# windows.py
# Contains the classes for all the major pop-up windows in the application.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from game_classes import StaffRole, PlayerPosition, ScoutingReport
from datetime import timedelta
import random
import os
from player_context_menu import PlayerContextMenu, add_player_context_menu

class RosterWindow(tk.Toplevel):
    """Enhanced Roster Management window with modern UI, advanced filtering, depth charts, and comprehensive team management."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(f"{parent.user_team.team_name} - Roster Management")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1600x1000")
        self.minsize(1400, 800)
        
        # State variables
        self.selected_players = {'nhl': set(), 'ahl': set(), 'prospects': set()}
        self.roster_filters = {
            'position': tk.StringVar(master=self, value="All"),
            'age_min': tk.StringVar(master=self, value=""),
            'age_max': tk.StringVar(master=self, value=""),
            'overall_min': tk.StringVar(master=self, value=""),
            'contract_status': tk.StringVar(master=self, value="All"),
            'injury_status': tk.StringVar(master=self, value="All")
        }
        self.sort_column = None
        self.sort_reverse = False
        
        # Player maps for treeviews
        self.player_maps = {'nhl': {}, 'ahl': {}, 'prospects': {}}
        
        # Initialize context menu manager
        self.context_menu_manager = PlayerContextMenu(self.parent)
        
        # Create the enhanced interface
        self.create_enhanced_interface()
        self.setup_styles()
        self.update_views()
        
        # Track window
        self.parent.open_windows['roster'] = self
    
    def create_enhanced_interface(self):
        """Create the comprehensive roster management interface."""
        # Main container
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header section with team overview
        self.create_header_section(main_container)
        
        # Main tabbed interface
        self.notebook = ttk.Notebook(main_container, style='Modern.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Enhanced NHL Roster tab
        self.create_enhanced_nhl_tab()
        
        # Enhanced AHL Roster tab
        self.create_enhanced_ahl_tab()
        
        # Enhanced Prospects tab
        self.create_enhanced_prospects_tab()
        
        # Depth Chart tab
        self.create_depth_chart_tab()
        
        # Salary Cap Management tab
        self.create_salary_cap_tab()
        
        # Action buttons footer
        self.create_action_footer(main_container)
    
    def create_header_section(self, parent):
        """Create header with team overview and quick stats."""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame', padding=(20, 15))
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Team name and logo area
        title_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        title_frame.pack(fill=tk.X)
        
        # Team title
        team_title = ttk.Label(
            title_frame,
            text=f"{self.parent.user_team.team_name.upper()} ROSTER",
            style='Title.TLabel',
            font=(self.parent.FONT_FAMILY, 18, 'bold')
        )
        team_title.pack(side=tk.LEFT)
        
        # Quick roster stats on the right
        stats_frame = ttk.Frame(title_frame, style='TitleBar.TFrame')
        stats_frame.pack(side=tk.RIGHT)
        
        # Calculate roster stats
        nhl_count = len(self.parent.user_team.roster)
        ahl_count = len(self.parent.user_team.ahl_roster)
        prospects_count = len(self.parent.user_team.prospects)
        total_players = nhl_count + ahl_count + prospects_count
        
        # Salary cap info
        current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) for p in self.parent.user_team.roster)
        cap_space = 83500000 - current_salary  # NHL salary cap
        
        # Stats display
        stats_text = f"NHL: {nhl_count}/23 | AHL: {ahl_count}/20 | Prospects: {prospects_count} | Cap Space: ${cap_space:,}"
        self.stats_label = ttk.Label(
            stats_frame,
            text=stats_text,
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 11)
        )
        self.stats_label.pack()
        
        # Subtitle with season info
        subtitle_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        subtitle_frame.pack(fill=tk.X, pady=(10, 0))
        
        season_info = f"Season: 2024-25 | Total Players: {total_players} | Last Updated: Today"
        ttk.Label(
            subtitle_frame,
            text=season_info,
            style='Subtitle.TLabel',
            font=(self.parent.FONT_FAMILY, 10)
        ).pack(side=tk.LEFT)
    
    def create_enhanced_nhl_tab(self):
        """Create enhanced NHL roster tab with filtering and management tools."""
        nhl_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(nhl_frame, text="NHL Roster (23)")
        
        # Toolbar for NHL roster
        self.create_roster_toolbar(nhl_frame, 'nhl')
        
        # Main content area
        content_frame = ttk.Frame(nhl_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # NHL roster treeview with enhanced columns
        nhl_columns = {
            'select': ('☐', 30),
            'jersey': ('#', 40),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'injury': ('Health', 80),
            'toi': ('TOI/GP', 60),
            'performance': ('Performance', 80)
        }
        
        self.nhl_tree = self.create_enhanced_treeview(content_frame, nhl_columns, 'nhl')
        
        # NHL roster summary
        self.create_roster_summary(content_frame, 'nhl')
    
    def create_enhanced_ahl_tab(self):
        """Create enhanced AHL roster tab."""
        ahl_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(ahl_frame, text="AHL Roster (20)")
        
        # Toolbar for AHL roster
        self.create_roster_toolbar(ahl_frame, 'ahl')
        
        # Main content area
        content_frame = ttk.Frame(ahl_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # AHL roster treeview
        ahl_columns = {
            'select': ('☐', 30),
            'jersey': ('#', 40),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'salary': ('Salary', 100),
            'contract': ('Contract', 80),
            'morale': ('Morale', 70),
            'readiness': ('NHL Ready', 80),
            'development': ('Development', 80)
        }
        
        self.ahl_tree = self.create_enhanced_treeview(content_frame, ahl_columns, 'ahl')
        
        # AHL roster summary
        self.create_roster_summary(content_frame, 'ahl')
    
    def create_enhanced_prospects_tab(self):
        """Create enhanced prospects tab."""
        prospects_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(prospects_frame, text="Prospects")
        
        # Toolbar for prospects
        self.create_roster_toolbar(prospects_frame, 'prospects')
        
        # Main content area
        content_frame = ttk.Frame(prospects_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Prospects treeview
        prospects_columns = {
            'select': ('☐', 30),
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 40),
            'ovr': ('OVR', 45),
            'pot': ('Pot', 45),
            'draft_year': ('Draft Year', 80),
            'draft_round': ('Round', 60),
            'league': ('League', 100),
            'development': ('Development', 80),
            'eta': ('ETA', 60)
        }
        
        self.prospects_tree = self.create_enhanced_treeview(content_frame, prospects_columns, 'prospects')
        
        # Prospects summary
        self.create_roster_summary(content_frame, 'prospects')
    
    def create_depth_chart_tab(self):
        """Create interactive depth chart tab."""
        depth_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(depth_frame, text="Depth Chart")
        
        # Depth chart header
        header_frame = ttk.Frame(depth_frame, style='Panel.TFrame', padding=15)
        header_frame.pack(fill=tk.X)
        
        ttk.Label(
            header_frame,
            text="TEAM DEPTH CHART",
            style='SubTitle.TLabel',
            font=(self.parent.FONT_FAMILY, 14, 'bold')
        ).pack()
        
        # Main depth chart area
        chart_frame = ttk.Frame(depth_frame, style='Panel.TFrame', padding=20)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create depth chart sections
        self.create_forwards_depth_chart(chart_frame)
        self.create_defense_depth_chart(chart_frame)
        self.create_goalies_depth_chart(chart_frame)
    
    def create_salary_cap_tab(self):
        """Create salary cap management tab."""
        cap_frame = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(cap_frame, text="Salary Cap")
        
        # Cap management header
        header_frame = ttk.Frame(cap_frame, style='Panel.TFrame', padding=15)
        header_frame.pack(fill=tk.X)
        
        ttk.Label(
            header_frame,
            text="SALARY CAP MANAGEMENT",
            style='SubTitle.TLabel',
            font=(self.parent.FONT_FAMILY, 14, 'bold')
        ).pack()
        
        # Cap overview
        self.create_cap_overview(cap_frame)
        
        # Contract details
        self.create_contract_breakdown(cap_frame)
    
    def create_roster_toolbar(self, parent, roster_type):
        """Create filtering and action toolbar for roster tabs."""
        toolbar_frame = ttk.Frame(parent, style='Panel.TFrame', padding=10)
        toolbar_frame.pack(fill=tk.X)
        
        # Filter section
        filter_frame = ttk.LabelFrame(toolbar_frame, text="Filters", )
        filter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        filter_content = ttk.Frame(filter_frame, style='Panel.TFrame', padding=5)
        filter_content.pack(fill=tk.X)
        
        # Position filter
        ttk.Label(filter_content, text="Position:", style='Content.TLabel').pack(side=tk.LEFT)
        pos_options = ["All", "F", "C", "LW", "RW", "D", "LD", "RD", "G"]
        pos_combo = ttk.Combobox(filter_content, textvariable=self.roster_filters['position'], 
                                values=pos_options, width=8, state='readonly')
        pos_combo.pack(side=tk.LEFT, padx=5)
        
        # Age filters
        ttk.Label(filter_content, text="Age:", style='Content.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        age_min_entry = ttk.Entry(filter_content, textvariable=self.roster_filters['age_min'], width=4)
        age_min_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(filter_content, text="to", style='Content.TLabel').pack(side=tk.LEFT)
        age_max_entry = ttk.Entry(filter_content, textvariable=self.roster_filters['age_max'], width=4)
        age_max_entry.pack(side=tk.LEFT, padx=2)
        
        # Overall rating filter
        ttk.Label(filter_content, text="Min OVR:", style='Content.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        ovr_entry = ttk.Entry(filter_content, textvariable=self.roster_filters['overall_min'], width=4)
        ovr_entry.pack(side=tk.LEFT, padx=2)
        
        # Apply filter button
        ttk.Button(filter_content, text="Apply Filters", 
                  command=lambda: self.apply_filters(roster_type),
                  style='TButton').pack(side=tk.LEFT, padx=10)
        
        # Action buttons section
        actions_frame = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        actions_frame.pack(side=tk.RIGHT)
        
        if roster_type == 'nhl':
            ttk.Button(actions_frame, text="Send to AHL", 
                      command=lambda: self.bulk_move_players('nhl', 'ahl'),
                      style='TButton').pack(side=tk.LEFT, padx=2)
            ttk.Button(actions_frame, text="Edit Lines", 
                      command=self.open_lines_editor,
                      style='Accent.TButton').pack(side=tk.LEFT, padx=2)
        elif roster_type == 'ahl':
            ttk.Button(actions_frame, text="Call Up", 
                      command=lambda: self.bulk_move_players('ahl', 'nhl'),
                      style='Accent.TButton').pack(side=tk.LEFT, padx=2)
            ttk.Button(actions_frame, text="Send to Prospects", 
                      command=lambda: self.bulk_move_players('ahl', 'prospects'),
                      style='TButton').pack(side=tk.LEFT, padx=2)
        elif roster_type == 'prospects':
            ttk.Button(actions_frame, text="Promote to AHL", 
                      command=lambda: self.bulk_move_players('prospects', 'ahl'),
                      style='Accent.TButton').pack(side=tk.LEFT, padx=2)
    
    def create_enhanced_treeview(self, parent, columns, roster_type):
        """Create an enhanced treeview with sorting and selection capabilities."""
        # Treeview frame
        tree_frame = ttk.Frame(parent, style='Panel.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create treeview
        tree = ttk.Treeview(tree_frame, columns=list(columns.keys()), show='headings', 
                           style='Enhanced.Treeview', height=20)
        
        # Configure columns
        for col, (text, width) in columns.items():
            tree.heading(col, text=text, command=lambda c=col: self.sort_treeview(tree, c, roster_type))
            tree.column(col, width=width, anchor='center' if col not in ['name'] else 'w')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind events
        tree.bind('<Button-1>', lambda e: self.handle_tree_click(e, tree, roster_type))
        tree.bind('<Double-1>', lambda e: self.handle_double_click(e, tree, roster_type))
        tree.bind('<Button-3>', lambda e: self.show_context_menu(e, tree, roster_type))
        
        return tree
    
    def create_roster_summary(self, parent, roster_type):
        """Create summary section for each roster tab."""
        summary_frame = ttk.Frame(parent, style='Panel.TFrame', padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Summary label
        summary_label = ttk.Label(summary_frame, text="", style='Summary.TLabel',
                                 font=(self.parent.FONT_FAMILY, 10))
        summary_label.pack(side=tk.LEFT)
        
        # Store summary label reference
        setattr(self, f'{roster_type}_summary_label', summary_label)
        
        # Selection actions on the right
        selection_frame = ttk.Frame(summary_frame, style='Panel.TFrame')
        selection_frame.pack(side=tk.RIGHT)
        
        ttk.Button(selection_frame, text="Select All", 
                  command=lambda: self.select_all_players(roster_type),
                  style='TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(selection_frame, text="Clear Selection", 
                  command=lambda: self.clear_selection(roster_type),
                  style='TButton').pack(side=tk.LEFT, padx=2)
    
    def create_forwards_depth_chart(self, parent):
        """Create forwards depth chart visualization."""
        forwards_frame = ttk.LabelFrame(parent, text="Forwards", )
        forwards_frame.pack(fill=tk.X, pady=5)
        
        content_frame = ttk.Frame(forwards_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.X)
        
        # Get forwards from roster sorted by overall rating
        forwards = [p for p in self.parent.user_team.roster 
                   if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Line structure
        lines = ["1st Line", "2nd Line", "3rd Line", "4th Line"]
        positions = ["LW", "C", "RW"]
        
        # Assign forwards to lines (top 12 forwards)
        line_assignments = {}
        for i in range(min(12, len(forwards))):
            line_num = i // 3
            pos_index = i % 3
            if line_num < 4:
                line_assignments[(line_num, pos_index)] = forwards[i]
        
        for i, line in enumerate(lines):
            line_frame = ttk.Frame(content_frame, style='Panel.TFrame')
            line_frame.pack(fill=tk.X, pady=2)
            
            # Line label
            ttk.Label(line_frame, text=line, style='Content.TLabel', width=10).pack(side=tk.LEFT)
            
            # Player positions
            for j, pos in enumerate(positions):
                player_frame = ttk.Frame(line_frame, style='Panel.TFrame', 
                                       relief='solid', borderwidth=1)
                player_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                
                # Get assigned player or show open slot
                assigned_player = line_assignments.get((i, j))
                if assigned_player:
                    player_text = f"{assigned_player.last_name} ({assigned_player.overall_rating()})"
                    player_label = ttk.Label(player_frame, text=player_text, 
                                           style='Content.TLabel', padding=5)
                else:
                    player_label = ttk.Label(player_frame, text=f"Open {pos}", 
                                           style='Content.TLabel', padding=5)
                player_label.pack()
    
    def create_defense_depth_chart(self, parent):
        """Create defense depth chart visualization."""
        defense_frame = ttk.LabelFrame(parent, text="Defense", )
        defense_frame.pack(fill=tk.X, pady=5)
        
        content_frame = ttk.Frame(defense_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.X)
        
        # Get defensemen from roster sorted by overall rating
        defensemen = [p for p in self.parent.user_team.roster 
                     if p.primary_position.value in ['LD', 'RD', 'D']]
        defensemen.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Defense pairs
        pairs = ["1st Pair", "2nd Pair", "3rd Pair"]
        
        # Assign defensemen to pairs (top 6 defensemen)
        pair_assignments = {}
        for i in range(min(6, len(defensemen))):
            pair_num = i // 2
            side = i % 2
            if pair_num < 3:
                pair_assignments[(pair_num, side)] = defensemen[i]
        
        for i, pair in enumerate(pairs):
            pair_frame = ttk.Frame(content_frame, style='Panel.TFrame')
            pair_frame.pack(fill=tk.X, pady=2)
            
            # Pair label
            ttk.Label(pair_frame, text=pair, style='Content.TLabel', width=10).pack(side=tk.LEFT)
            
            # Defense positions
            for j, pos in enumerate(["LD", "RD"]):
                player_frame = ttk.Frame(pair_frame, style='Panel.TFrame', 
                                       relief='solid', borderwidth=1)
                player_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                
                # Get assigned player or show open slot
                assigned_player = pair_assignments.get((i, j))
                if assigned_player:
                    player_text = f"{assigned_player.last_name} ({assigned_player.overall_rating()})"
                    player_label = ttk.Label(player_frame, text=player_text, 
                                           style='Content.TLabel', padding=5)
                else:
                    player_label = ttk.Label(player_frame, text=f"Open {pos}", 
                                           style='Content.TLabel', padding=5)
                player_label.pack()
    
    def create_goalies_depth_chart(self, parent):
        """Create goalies depth chart visualization."""
        goalies_frame = ttk.LabelFrame(parent, text="Goalies", )
        goalies_frame.pack(fill=tk.X, pady=5)
        
        content_frame = ttk.Frame(goalies_frame, style='Panel.TFrame', padding=10)
        content_frame.pack(fill=tk.X)
        
        # Get goalies from roster sorted by overall rating
        goalies = [p for p in self.parent.user_team.roster 
                  if p.primary_position.value == 'G']
        goalies.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        for i, role in enumerate(["Starter", "Backup"]):
            goalie_frame = ttk.Frame(content_frame, style='Panel.TFrame')
            goalie_frame.pack(fill=tk.X, pady=2)
            
            # Role label
            ttk.Label(goalie_frame, text=role, style='Content.TLabel', width=10).pack(side=tk.LEFT)
            
            # Goalie slot
            player_frame = ttk.Frame(goalie_frame, style='Panel.TFrame', 
                                   relief='solid', borderwidth=1)
            player_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # Get assigned goalie or show open slot
            if i < len(goalies):
                goalie = goalies[i]
                player_text = f"{goalie.last_name} ({goalie.overall_rating()})"
                player_label = ttk.Label(player_frame, text=player_text, 
                                       style='Content.TLabel', padding=5)
            else:
                player_label = ttk.Label(player_frame, text="Open G", 
                                       style='Content.TLabel', padding=5)
            player_label.pack()
    
    def create_cap_overview(self, parent):
        """Create salary cap overview section."""
        overview_frame = ttk.Frame(parent, style='Panel.TFrame', padding=20)
        overview_frame.pack(fill=tk.X)
        
        # Cap info grid
        info_frame = ttk.Frame(overview_frame, style='Panel.TFrame')
        info_frame.pack(fill=tk.X)
        
        # Calculate salary cap info
        salary_cap = 83500000
        current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) 
                           for p in self.parent.user_team.roster)
        cap_space = salary_cap - current_salary
        cap_percentage = (current_salary / salary_cap) * 100
        
        # Cap visualization
        cap_labels = [
            ("Salary Cap:", f"${salary_cap:,}"),
            ("Current Payroll:", f"${current_salary:,}"),
            ("Cap Space:", f"${cap_space:,}"),
            ("Cap Usage:", f"{cap_percentage:.1f}%")
        ]
        
        for i, (label, value) in enumerate(cap_labels):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(info_frame, text=label, style='Info.TLabel').grid(row=row, column=col, sticky='w', padx=5, pady=2)
            value_label = ttk.Label(info_frame, text=value, style='Value.TLabel', 
                                  font=(self.parent.FONT_FAMILY, 11, 'bold'))
            value_label.grid(row=row, column=col+1, sticky='w', padx=5, pady=2)
    
    def create_contract_breakdown(self, parent):
        """Create detailed contract breakdown."""
        breakdown_frame = ttk.Frame(parent, style='Panel.TFrame', padding=20)
        breakdown_frame.pack(fill=tk.BOTH, expand=True)
        
        # Contract treeview
        contract_columns = {
            'name': ('Player', 200),
            'pos': ('Pos', 50),
            'salary': ('Salary', 100),
            'years_left': ('Years Left', 80),
            'total_value': ('Total Value', 100),
            'cap_hit': ('Cap Hit', 100),
            'status': ('Status', 100)
        }
        
        self.contract_tree = ttk.Treeview(breakdown_frame, columns=list(contract_columns.keys()), 
                                   show='headings', height=15)
        
        for col, (text, width) in contract_columns.items():
            self.contract_tree.heading(col, text=text)
            self.contract_tree.column(col, width=width, anchor='center' if col != 'name' else 'w')
        
        # Scrollbar for contracts
        contract_scroll = ttk.Scrollbar(breakdown_frame, orient="vertical", command=self.contract_tree.yview)
        self.contract_tree.configure(yscrollcommand=contract_scroll.set)
        
        self.contract_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        contract_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate contract data
        self.populate_contract_tree()
    
    def populate_contract_tree(self):
        """Populate the contract breakdown treeview."""
        # Clear existing items
        self.contract_tree.delete(*self.contract_tree.get_children())
        
        # Get all NHL roster players
        for player in sorted(self.parent.user_team.roster, key=lambda p: p.overall_rating(), reverse=True):
            # Get contract details
            salary = getattr(player, 'salary', getattr(player.contract, 'salary', 750000))
            years_left = getattr(player, 'contract_years', getattr(player.contract, 'years_remaining', 0))
            total_value = salary * years_left
            cap_hit = salary  # For simplicity, assuming cap hit equals salary
            
            # Determine status
            if years_left <= 1:
                status = "Expiring"
            elif years_left <= 2:
                status = "Short-term"
            else:
                status = "Long-term"
            
            # Insert into tree
            values = [
                player.full_name,
                player.primary_position.value,
                f"${salary:,}",
                str(years_left),
                f"${total_value:,}",
                f"${cap_hit:,}",
                status
            ]
            
            self.contract_tree.insert('', 'end', values=values)
    
    def create_action_footer(self, parent):
        """Create action buttons footer."""
        footer_frame = ttk.Frame(parent, style='Panel.TFrame', padding=(0, 15, 0, 0))
        footer_frame.pack(fill=tk.X)
        
        # Left side actions
        left_actions = ttk.Frame(footer_frame, style='Panel.TFrame')
        left_actions.pack(side=tk.LEFT)
        
        ttk.Button(left_actions, text="Trade Block", 
                  command=self.parent.open_trade_block_window,
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(left_actions, text="Contract Extensions", 
                  command=self.parent.open_contract_extensions_window,
                  style='TButton').pack(side=tk.LEFT, padx=5)
        
        # Right side actions
        right_actions = ttk.Frame(footer_frame, style='Panel.TFrame')
        right_actions.pack(side=tk.RIGHT)
        
        ttk.Button(right_actions, text="Export Roster", 
                  command=self.export_roster,
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(right_actions, text="Refresh", 
                  command=self.update_views,
                  style='TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(right_actions, text="Close", 
                  command=self.destroy,
                  style='TButton').pack(side=tk.LEFT, padx=5)
    
    def setup_styles(self):
        """Setup custom styles for the roster window."""
        style = ttk.Style()
        
        # Enhanced treeview style
        style.configure('Enhanced.Treeview', 
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR,
                       fieldbackground=self.parent.CONTENT_BG,
                       borderwidth=0,
                       font=(self.parent.FONT_FAMILY, 9))
        
        style.configure('Enhanced.Treeview.Heading',
                       background=self.parent.TITLE_BAR_COLOR,
                       foreground=self.parent.HEADER_COLOR,
                       font=(self.parent.FONT_FAMILY, 9, 'bold'))
    
    def populate_roster_tree(self, tree, players, roster_type):
        """Populate treeview with player data."""
        # Clear existing items
        tree.delete(*tree.get_children())
        self.player_maps[roster_type] = {}
        
        for player in sorted(players, key=lambda p: p.overall_rating(), reverse=True):
            # Selection checkbox
            is_selected = player.id in self.selected_players[roster_type]
            checkbox = "☑" if is_selected else "☐"
            
            # Get player info
            name = player.full_name
            position = player.primary_position.value
            age = player.age
            overall = player.overall_rating()
            potential = getattr(player, 'potential_grade', 'C')
            
            # Contract info
            salary = getattr(player, 'salary', getattr(player.contract, 'salary', 750000))
            contract_years = getattr(player, 'contract_years', getattr(player.contract, 'years_remaining', 0))
            
            # Morale and health
            morale = f"{player.morale}/20"
            injury_status = getattr(player, 'injury_status', 'Healthy')
            
            # Basic values for all roster types
            values = [checkbox, getattr(player, 'jersey_number', ''), name, position, 
                     age, overall, potential, f"${salary:,}", f"{contract_years}y", morale]
            
            # Add roster-specific columns
            if roster_type == 'nhl':
                toi = getattr(player, 'average_toi', '0:00')
                performance = self.calculate_performance_rating(player)
                values.extend([injury_status, toi, performance])
            elif roster_type == 'ahl':
                readiness = self.calculate_nhl_readiness(player)
                development = self.calculate_development_trend(player)
                values.extend([readiness, development])
            elif roster_type == 'prospects':
                draft_year = getattr(player, 'draft_year', 'Undrafted')
                draft_round = getattr(player, 'draft_round', 'FA')
                league = getattr(player, 'current_league', 'Amateur')
                development = self.calculate_development_trend(player)
                eta = self.calculate_eta(player)
                # Remove salary and contract columns for prospects, add prospect-specific data
                values = [checkbox, name, position, age, overall, potential, 
                         draft_year, draft_round, league, development, eta]
            
            # Insert item
            item_id = tree.insert('', 'end', values=values)
            self.player_maps[roster_type][item_id] = player
            
            # Apply tags for visual styling
            tags = []
            if is_selected:
                tags.append('selected')
            if injury_status != 'Healthy':
                tags.append('injured')
            if overall >= 85:
                tags.append('elite')
            elif overall >= 80:
                tags.append('star')
            
            if tags:
                tree.set(item_id, tags=tags)
    
    def calculate_performance_rating(self, player):
        """Calculate performance rating for NHL players."""
        # This would be based on season stats
        base_performance = player.overall_rating()
        # Add some variation based on morale and recent play
        variation = (player.morale - 10) * 2
        performance = max(0, min(100, base_performance + variation))
        return f"{performance}"
    
    def calculate_nhl_readiness(self, player):
        """Calculate NHL readiness percentage for AHL players."""
        readiness = min(100, max(0, (player.overall_rating() - 65) * 2.5))
        return f"{readiness:.0f}%"
    
    def calculate_development_trend(self, player):
        """Calculate development trend."""
        if player.age <= 20:
            return "Rapid ↗"
        elif player.age <= 23:
            return "Steady ↗"
        elif player.age <= 26:
            return "Slow ↗"
        else:
            return "Stable →"
    
    def calculate_eta(self, player):
        """Calculate estimated time of arrival for prospects."""
        if player.overall_rating() >= 75:
            return "Ready"
        elif player.overall_rating() >= 70:
            return "1-2 years"
        elif player.overall_rating() >= 65:
            return "2-3 years"
        else:
            return "3+ years"
    
    def handle_tree_click(self, event, tree, roster_type):
        """Handle tree click events."""
        region = tree.identify_region(event.x, event.y)
        if region == 'cell':
            col = tree.identify_column(event.x)
            if col == '#1':  # Selection column
                item_id = tree.identify_row(event.y)
                if item_id:
                    self.toggle_player_selection(item_id, tree, roster_type)
    
    def handle_double_click(self, event, tree, roster_type):
        """Handle double-click to open player profile."""
        item_id = tree.identify_row(event.y)
        if item_id and item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]
            self.parent.open_player_profile(player)
    
    def show_context_menu(self, event, tree, roster_type):
        """Show enhanced context menu for player actions using universal system."""
        item_id = tree.identify_row(event.y)
        if item_id and item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]
            
            # Create roster-specific additional options
            roster_options = []
            
            if roster_type == 'nhl':
                roster_options = [
                    ("📉 Send to AHL", lambda: self.move_player(player, 'nhl', 'ahl')),
                    ("🔄 Add to Trade Block", lambda: self.add_to_trade_block(player))
                ]
            elif roster_type == 'ahl':
                roster_options = [
                    ("📈 Call up to NHL", lambda: self.move_player(player, 'ahl', 'nhl')),
                    ("📉 Send to Prospects", lambda: self.move_player(player, 'ahl', 'prospects'))
                ]
            elif roster_type == 'prospects':
                roster_options = [
                    ("📈 Promote to AHL", lambda: self.move_player(player, 'prospects', 'ahl'))
                ]
            
            # Add contract options
            roster_options.append(("📝 Contract Extension", 
                                 lambda: self.parent.open_contract_negotiation_window(player, True)))
            
            # Use universal context menu
            if not hasattr(self, 'context_menu_manager'):
                self.context_menu_manager = PlayerContextMenu(self.parent)
            
            self.context_menu_manager.show_context_menu(event, player, roster_options)
    
    def toggle_player_selection(self, item_id, tree, roster_type):
        """Toggle player selection state."""
        if item_id in self.player_maps[roster_type]:
            player = self.player_maps[roster_type][item_id]
            
            if player.id in self.selected_players[roster_type]:
                self.selected_players[roster_type].remove(player.id)
                checkbox = "☐"
            else:
                self.selected_players[roster_type].add(player.id)
                checkbox = "☑"
            
            # Update checkbox display
            values = list(tree.item(item_id, 'values'))
            values[0] = checkbox
            tree.item(item_id, values=values)
            
            self.update_roster_summary(roster_type)
    
    def sort_treeview(self, tree, col, roster_type):
        """Sort treeview by column."""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        
        # Get all items
        items = list(tree.get_children())
        
        # Sort based on column
        def get_sort_key(item_id):
            values = tree.item(item_id, 'values')
            col_index = list(tree['columns']).index(col)
            value = values[col_index] if col_index < len(values) else ''
            
            # Handle numeric columns
            if col in ['age', 'ovr', 'pot']:
                try:
                    return int(value)
                except:
                    return 0
            elif col == 'salary':
                try:
                    return int(value.replace('$', '').replace(',', ''))
                except:
                    return 0
            return str(value).lower()
        
        items.sort(key=get_sort_key, reverse=self.sort_reverse)
        
        # Reorder items in tree
        for i, item_id in enumerate(items):
            tree.move(item_id, '', i)
    
    def apply_filters(self, roster_type):
        """Apply filters to roster view."""
        # This would filter the displayed players based on the filter criteria
        self.update_roster_tab(roster_type)
    
    def update_roster_tab(self, roster_type):
        """Update specific roster tab."""
        if roster_type == 'nhl':
            self.populate_roster_tree(self.nhl_tree, self.parent.user_team.roster, 'nhl')
        elif roster_type == 'ahl':
            self.populate_roster_tree(self.ahl_tree, self.parent.user_team.ahl_roster, 'ahl')
        elif roster_type == 'prospects':
            self.populate_roster_tree(self.prospects_tree, self.parent.user_team.prospects, 'prospects')
        
        self.update_roster_summary(roster_type)
    
    def update_roster_summary(self, roster_type):
        """Update roster summary information."""
        if roster_type == 'nhl':
            players = self.parent.user_team.roster
            selected_count = len(self.selected_players['nhl'])
            total_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) for p in players)
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(p.overall_rating() for p in players) / len(players) if players else 0
            
            summary = f"Players: {len(players)}/23 | Selected: {selected_count} | Total Salary: ${total_salary:,} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.nhl_summary_label.config(text=summary)
        
        elif roster_type == 'ahl':
            players = self.parent.user_team.ahl_roster
            selected_count = len(self.selected_players['ahl'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            avg_overall = sum(p.overall_rating() for p in players) / len(players) if players else 0
            
            summary = f"Players: {len(players)}/20 | Selected: {selected_count} | Avg Age: {avg_age:.1f} | Avg OVR: {avg_overall:.1f}"
            self.ahl_summary_label.config(text=summary)
        
        elif roster_type == 'prospects':
            players = self.parent.user_team.prospects
            selected_count = len(self.selected_players['prospects'])
            avg_age = sum(p.age for p in players) / len(players) if players else 0
            high_potential = len([p for p in players if getattr(p, 'potential_grade', 'C') in ['A+', 'A', 'A-']])
            
            summary = f"Prospects: {len(players)} | Selected: {selected_count} | High Potential: {high_potential} | Avg Age: {avg_age:.1f}"
            self.prospects_summary_label.config(text=summary)
    
    def select_all_players(self, roster_type):
        """Select all players in the roster."""
        if roster_type == 'nhl':
            players = self.parent.user_team.roster
        elif roster_type == 'ahl':
            players = self.parent.user_team.ahl_roster
        else:
            players = self.parent.user_team.prospects
        
        self.selected_players[roster_type] = {p.id for p in players}
        self.update_roster_tab(roster_type)
    
    def clear_selection(self, roster_type):
        """Clear all player selections."""
        self.selected_players[roster_type].clear()
        self.update_roster_tab(roster_type)
    
    def bulk_move_players(self, from_roster, to_roster):
        """Move selected players between rosters."""
        selected_ids = self.selected_players[from_roster].copy()
        
        if not selected_ids:
            tk.messagebox.showinfo("No Selection", "Please select players to move.")
            return
        
        # Get source and destination lists
        if from_roster == 'nhl':
            source_list = self.parent.user_team.roster
        elif from_roster == 'ahl':
            source_list = self.parent.user_team.ahl_roster
        else:
            source_list = self.parent.user_team.prospects
        
        # Move players
        players_to_move = [p for p in source_list if p.id in selected_ids]
        
        for player in players_to_move:
            self.move_player(player, from_roster, to_roster)
        
        # Clear selections and update views
        self.selected_players[from_roster].clear()
        self.update_views()
    
    def move_player(self, player, from_roster, to_roster):
        """Move a single player between rosters."""
        # Remove from source
        if from_roster == 'nhl':
            self.parent.user_team.roster.remove(player)
        elif from_roster == 'ahl':
            self.parent.user_team.ahl_roster.remove(player)
        else:
            self.parent.user_team.prospects.remove(player)
        
        # Add to destination
        if to_roster == 'nhl':
            self.parent.user_team.roster.append(player)
        elif to_roster == 'ahl':
            self.parent.user_team.ahl_roster.append(player)
        else:
            self.parent.user_team.prospects.append(player)
        
        # Update any open windows
        self.parent.update_all_views()
    
    def add_to_trade_block(self, player):
        """Add player to trade block."""
        if not hasattr(self.parent, 'trade_block'):
            self.parent.trade_block = []
        
        if player not in self.parent.trade_block:
            self.parent.trade_block.append(player)
            tk.messagebox.showinfo("Trade Block", f"{player.full_name} added to trade block.")
        else:
            tk.messagebox.showinfo("Trade Block", f"{player.full_name} is already on the trade block.")
    
    def open_lines_editor(self):
        """Open the lines editor."""
        # This would open the existing lines editor
        pass
    
    def export_roster(self):
        """Export roster to CSV file."""
        try:
            from datetime import datetime
            import csv
            import os
            
            # Create exports directory if it doesn't exist
            exports_dir = "exports"
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"roster_export_{self.parent.user_team.team_name.replace(' ', '_')}_{timestamp}.csv"
            filepath = os.path.join(exports_dir, filename)
            
            # Collect all roster data
            roster_data = []
            
            # Add NHL roster
            for player in self.parent.user_team.roster:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0
                
                roster_data.append([
                    "NHL",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    player.overall_rating(),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])
            
            # Add AHL roster
            for player in self.parent.user_team.ahl_roster:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0
                
                roster_data.append([
                    "AHL",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    player.overall_rating(),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])
            
            # Add Prospects
            for player in self.parent.user_team.prospects:
                contract = player.contract
                salary = getattr(contract, 'salary', 750000) if contract else 750000
                years_remaining = getattr(contract, 'years_remaining', 0) if contract else 0
                
                roster_data.append([
                    "Prospects",
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    player.overall_rating(),
                    f"${salary:,}",
                    years_remaining,
                    getattr(player, 'games_played', 0),
                    getattr(player, 'goals', 0),
                    getattr(player, 'assists', 0),
                    getattr(player, 'points', 0),
                    getattr(player, 'plus_minus', 0)
                ])
            
            # Write to CSV
            headers = ["Level", "Name", "Position", "Age", "Overall", "Salary", "Years Left", 
                      "GP", "G", "A", "PTS", "+/-"]
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(roster_data)
            
            tk.messagebox.showinfo("Export Successful", 
                                 f"Roster exported successfully!\n\n"
                                 f"File: {filename}\n"
                                 f"Location: {exports_dir}\n"
                                 f"Players exported: {len(roster_data)}")
                                 
        except Exception as e:
            print(f"Error exporting roster: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export roster:\n{str(e)}")
    
    def update_views(self):
        """Update all roster views."""
        self.update_roster_tab('nhl')
        self.update_roster_tab('ahl')
        self.update_roster_tab('prospects')
        
        # Update header stats
        nhl_count = len(self.parent.user_team.roster)
        ahl_count = len(self.parent.user_team.ahl_roster)
        prospects_count = len(self.parent.user_team.prospects)
        
        current_salary = sum(getattr(p, 'salary', getattr(p.contract, 'salary', 750000)) 
                           for p in self.parent.user_team.roster)
        cap_space = 83500000 - current_salary
        
        stats_text = f"NHL: {nhl_count}/23 | AHL: {ahl_count}/20 | Prospects: {prospects_count} | Cap Space: ${cap_space:,}"
        self.stats_label.config(text=stats_text)
        
        # Update tab labels with counts
        self.notebook.tab(0, text=f"NHL Roster ({nhl_count})")
        self.notebook.tab(1, text=f"AHL Roster ({ahl_count})")
        self.notebook.tab(2, text=f"Prospects ({prospects_count})")
        
        # Update depth chart and salary cap if those tabs exist
        try:
            # Refresh depth chart by recreating the sections
            current_tab = self.notebook.index(self.notebook.select())
            if current_tab == 3:  # Depth Chart tab
                self.refresh_depth_chart()
            elif current_tab == 4:  # Salary Cap tab
                self.refresh_salary_cap()
        except (tk.TclError, AttributeError):
            # Tab might not exist or be selected
            pass
    
    def refresh_depth_chart(self):
        """Refresh the depth chart with current roster data."""
        # Find the depth chart tab content and refresh it
        try:
            depth_tab = self.notebook.nametowidget(self.notebook.tabs()[3])
            # Clear and recreate the depth chart sections
            for widget in depth_tab.winfo_children():
                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Frame) and hasattr(child, 'winfo_children'):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, ttk.LabelFrame):
                                    grandchild.destroy()
            
            # Find the main chart frame and recreate content
            for widget in depth_tab.winfo_children():
                if isinstance(widget, ttk.Frame):
                    # Recreate depth chart sections
                    self.create_forwards_depth_chart(widget)
                    self.create_defense_depth_chart(widget)
                    self.create_goalies_depth_chart(widget)
                    break
        except (IndexError, tk.TclError):
            pass
    
    def refresh_salary_cap(self):
        """Refresh the salary cap information."""
        try:
            # Update contract tree if it exists
            if hasattr(self, 'contract_tree'):
                self.populate_contract_tree()
        except (AttributeError, tk.TclError):
            pass

class FreeAgencyWindow(tk.Toplevel):
    """Enhanced Free Agency window with modern UI, advanced filtering, and comprehensive management tools."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Free Agency Market - Hockey Manager")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # State variables
        self.selected_players = []
        self.selected_staff = []
        self.player_filters = {}
        self.staff_filters = {}
        
        # Create the enhanced interface
        self.create_enhanced_interface()
        self.setup_styles()
        self.update_views()
        
        # Track window
        self.parent.open_windows['free_agency'] = self
    
    def create_enhanced_interface(self):
        """Create the modern, comprehensive free agency interface."""
        # Main container with professional styling
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header section with market overview
        self.create_header_section(main_container)
        
        # Main tabbed interface
        self.notebook = ttk.Notebook(main_container, style='Modern.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Enhanced Player tab
        self.create_enhanced_player_tab()
        
        # Enhanced Staff tab  
        self.create_enhanced_staff_tab()
        
        # Market Overview tab
        self.create_market_overview_tab()
        
        # Action buttons footer
        self.create_action_footer(main_container)
    
    def create_header_section(self, parent):
        """Create the header with market overview and quick stats."""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame', padding=(20, 15))
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title and subtitle
        title_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame,
            text="FREE AGENCY MARKET",
            style='Title.TLabel',
            font=(self.parent.FONT_FAMILY, 18, 'bold')
        ).pack(side=tk.LEFT)
        
        # Quick stats on the right
        stats_frame = ttk.Frame(title_frame, style='TitleBar.TFrame')
        stats_frame.pack(side=tk.RIGHT)
        
        # Market stats
        player_count = len(self.parent.game_manager.free_agents)
        staff_count = len(self.parent.league.free_agent_staff)
        
        stats_text = f"Available: {player_count} Players • {staff_count} Staff"
        ttk.Label(
            stats_frame,
            text=stats_text,
            style='Subtitle.TLabel',
            font=(self.parent.FONT_FAMILY, 12)
        ).pack(side=tk.RIGHT)
        
        # Subtitle with current date/season info
        subtitle_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        subtitle_frame.pack(fill=tk.X, pady=(5, 0))
        
        season_info = f"Season 2024-25 • Free Agency Period"
        ttk.Label(
            subtitle_frame,
            text=season_info,
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 11)
        ).pack(side=tk.LEFT)
        
        # Team cap space on the right
        user_team = self.parent.game_manager.user_team
        current_salary = sum(getattr(p, "salary", getattr(p.contract, "salary", 750000)) for p in user_team.roster)
        cap_space = 83500000 - current_salary  # NHL salary cap
        
        cap_text = f"Available Cap Space: ${cap_space:,}"
        cap_color = self.parent.ACCENT_COLOR if cap_space > 10000000 else "#FFC107" if cap_space > 0 else "#F44336"
        
        cap_label = ttk.Label(
            subtitle_frame,
            text=cap_text,
            font=(self.parent.FONT_FAMILY, 11, 'bold'),
            foreground=cap_color
        )
        cap_label.pack(side=tk.RIGHT)
    
    def create_enhanced_player_tab(self):
        """Create the enhanced player free agency tab with advanced features."""
        player_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(player_tab, text="Free Agent Players")
        
        # Filter section
        filter_frame = ttk.LabelFrame(player_tab, text="Player Filters & Search", padding=15)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # First row of filters
        filter_row1 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row1.pack(fill=tk.X, pady=(0, 10))
        
        # Name search
        ttk.Label(filter_row1, text="Name:", style='Content.TLabel').grid(row=0, column=0, padx=(0, 5), pady=2, sticky='w')
        self.player_name_search = ttk.Entry(filter_row1, width=15, font=(self.parent.FONT_FAMILY, 10))
        self.player_name_search.grid(row=0, column=1, padx=(0, 15), pady=2)
        self.player_name_search.bind('<KeyRelease>', self.filter_players)
        
        # Position filter
        ttk.Label(filter_row1, text="Position:", style='Content.TLabel').grid(row=0, column=2, padx=(0, 5), pady=2, sticky='w')
        positions = ['All', 'C', 'LW', 'RW', 'LD', 'RD', 'D', 'G']
        self.player_position_filter = ttk.Combobox(filter_row1, values=positions, state='readonly', width=8)
        self.player_position_filter.set('All')
        self.player_position_filter.grid(row=0, column=3, padx=(0, 15), pady=2)
        self.player_position_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Age range
        ttk.Label(filter_row1, text="Age:", style='Content.TLabel').grid(row=0, column=4, padx=(0, 5), pady=2, sticky='w')
        age_ranges = ['All', '18-22', '23-26', '27-30', '31-35', '36+']
        self.player_age_filter = ttk.Combobox(filter_row1, values=age_ranges, state='readonly', width=10)
        self.player_age_filter.set('All')
        self.player_age_filter.grid(row=0, column=5, padx=(0, 15), pady=2)
        self.player_age_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Overall rating
        ttk.Label(filter_row1, text="Rating:", style='Content.TLabel').grid(row=0, column=6, padx=(0, 5), pady=2, sticky='w')
        rating_ranges = ['All', '85+', '80-84', '75-79', '70-74', '65-69', '60-64', '<60']
        self.player_rating_filter = ttk.Combobox(filter_row1, values=rating_ranges, state='readonly', width=10)
        self.player_rating_filter.set('All')
        self.player_rating_filter.grid(row=0, column=7, padx=(0, 15), pady=2)
        self.player_rating_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Second row of filters
        filter_row2 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row2.pack(fill=tk.X, pady=(0, 10))
        
        # Salary range
        ttk.Label(filter_row2, text="Salary:", style='Content.TLabel').grid(row=0, column=0, padx=(0, 5), pady=2, sticky='w')
        salary_ranges = ['All', 'Under $1M', '$1M-$3M', '$3M-$5M', '$5M-$8M', 'Over $8M']
        self.player_salary_filter = ttk.Combobox(filter_row2, values=salary_ranges, state='readonly', width=12)
        self.player_salary_filter.set('All')
        self.player_salary_filter.grid(row=0, column=1, padx=(0, 15), pady=2)
        self.player_salary_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Contract length
        ttk.Label(filter_row2, text="Contract:", style='Content.TLabel').grid(row=0, column=2, padx=(0, 5), pady=2, sticky='w')
        contract_lengths = ['All', '1 Year', '2 Years', '3-4 Years', '5+ Years']
        self.player_contract_filter = ttk.Combobox(filter_row2, values=contract_lengths, state='readonly', width=10)
        self.player_contract_filter.set('All')
        self.player_contract_filter.grid(row=0, column=3, padx=(0, 15), pady=2)
        self.player_contract_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Sort options
        ttk.Label(filter_row2, text="Sort by:", style='Content.TLabel').grid(row=0, column=4, padx=(0, 5), pady=2, sticky='w')
        sort_options = ['Overall Rating', 'Age', 'Name', 'Position', 'Salary', 'Potential']
        self.player_sort_filter = ttk.Combobox(filter_row2, values=sort_options, state='readonly', width=12)
        self.player_sort_filter.set('Overall Rating')
        self.player_sort_filter.grid(row=0, column=5, padx=(0, 15), pady=2)
        self.player_sort_filter.bind('<<ComboboxSelected>>', self.filter_players)
        
        # Clear filters button
        ttk.Button(
            filter_row2,
            text="Clear Filters",
            style='Secondary.TButton',
            command=self.clear_player_filters
        ).grid(row=0, column=6, padx=(15, 0), pady=2)
        
        # Results and selection info
        info_frame = ttk.Frame(player_tab, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.player_results_label = ttk.Label(
            info_frame,
            text="Showing 0 players",
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 10)
        )
        self.player_results_label.pack(side=tk.LEFT)
        
        self.player_selection_label = ttk.Label(
            info_frame,
            text="",
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 10)
        )
        self.player_selection_label.pack(side=tk.RIGHT)
        
        # Enhanced player list with more columns
        list_frame = ttk.Frame(player_tab, style='Panel.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        player_columns = {
            'name': ('Name', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'pot': ('Pot', 50),
            'salary': ('Salary', 100),
            'years': ('Years', 60),
            'nationality': ('Country', 80),
            'shoots': ('Shoots', 60),
            'height': ('Height', 60),
            'weight': ('Weight', 60)
        }
        
        self.fa_player_tree = self.parent._create_treeview(list_frame, player_columns, height=25)
        self.fa_player_tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        add_player_context_menu(self.fa_player_tree, self)
        self.fa_player_tree.bind('<Double-1>', self.negotiate_with_player)
        self.fa_player_tree.bind('<<TreeviewSelect>>', self.on_player_selection_changed)
        
        # Action buttons for players
        player_actions = ttk.Frame(player_tab, style='Panel.TFrame')
        player_actions.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            player_actions,
            text="Sign Selected Player",
            style='Accent.TButton',
            command=self.sign_selected_player
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            player_actions,
            text="View Player Profile",
            style='TButton',
            command=self.view_selected_player_profile
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            player_actions,
            text="Compare Players",
            style='TButton',
            command=self.compare_selected_players
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            player_actions,
            text="Market Analysis",
            style='TButton',
            command=self.show_player_market_analysis
        ).pack(side=tk.LEFT, padx=(0, 10))
    
    def create_enhanced_staff_tab(self):
        """Create the enhanced staff free agency tab with advanced features."""
        staff_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(staff_tab, text="Free Agent Staff")
        
        # Filter section for staff
        filter_frame = ttk.LabelFrame(staff_tab, text="Staff Filters & Search", padding=15)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # First row of staff filters
        filter_row1 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row1.pack(fill=tk.X, pady=(0, 10))
        
        # Name search
        ttk.Label(filter_row1, text="Name:", style='Content.TLabel').grid(row=0, column=0, padx=(0, 5), pady=2, sticky='w')
        self.staff_name_search = ttk.Entry(filter_row1, width=15, font=(self.parent.FONT_FAMILY, 10))
        self.staff_name_search.grid(row=0, column=1, padx=(0, 15), pady=2)
        self.staff_name_search.bind('<KeyRelease>', self.filter_staff)
        
        # Role filter
        ttk.Label(filter_row1, text="Role:", style='Content.TLabel').grid(row=0, column=2, padx=(0, 5), pady=2, sticky='w')
        from game_classes import StaffRole
        roles = ['All'] + [role.value for role in StaffRole]
        self.staff_role_filter = ttk.Combobox(filter_row1, values=roles, state='readonly', width=20)
        self.staff_role_filter.set('All')
        self.staff_role_filter.grid(row=0, column=3, padx=(0, 15), pady=2)
        self.staff_role_filter.bind('<<ComboboxSelected>>', self.filter_staff)
        
        # Department filter
        ttk.Label(filter_row1, text="Department:", style='Content.TLabel').grid(row=0, column=4, padx=(0, 5), pady=2, sticky='w')
        departments = ['All', 'Management', 'Coaching', 'Development', 'Scouting', 'Medical', 'Analytics']
        self.staff_department_filter = ttk.Combobox(filter_row1, values=departments, state='readonly', width=12)
        self.staff_department_filter.set('All')
        self.staff_department_filter.grid(row=0, column=5, padx=(0, 15), pady=2)
        self.staff_department_filter.bind('<<ComboboxSelected>>', self.filter_staff)
        
        # Second row of staff filters
        filter_row2 = ttk.Frame(filter_frame, style='Panel.TFrame')
        filter_row2.pack(fill=tk.X)
        
        # Experience filter
        ttk.Label(filter_row2, text="Experience:", style='Content.TLabel').grid(row=0, column=0, padx=(0, 5), pady=2, sticky='w')
        experience_ranges = ['All', '0-2 Years', '3-5 Years', '6-10 Years', '11-15 Years', '16+ Years']
        self.staff_experience_filter = ttk.Combobox(filter_row2, values=experience_ranges, state='readonly', width=12)
        self.staff_experience_filter.set('All')
        self.staff_experience_filter.grid(row=0, column=1, padx=(0, 15), pady=2)
        self.staff_experience_filter.bind('<<ComboboxSelected>>', self.filter_staff)
        
        # Salary filter
        ttk.Label(filter_row2, text="Salary:", style='Content.TLabel').grid(row=0, column=2, padx=(0, 5), pady=2, sticky='w')
        staff_salary_ranges = ['All', 'Under $100k', '$100k-$250k', '$250k-$500k', '$500k-$1M', 'Over $1M']
        self.staff_salary_filter = ttk.Combobox(filter_row2, values=staff_salary_ranges, state='readonly', width=12)
        self.staff_salary_filter.set('All')
        self.staff_salary_filter.grid(row=0, column=3, padx=(0, 15), pady=2)
        self.staff_salary_filter.bind('<<ComboboxSelected>>', self.filter_staff)
        
        # Sort options for staff
        ttk.Label(filter_row2, text="Sort by:", style='Content.TLabel').grid(row=0, column=4, padx=(0, 5), pady=2, sticky='w')
        staff_sort_options = ['Overall Rating', 'Name', 'Role', 'Experience', 'Salary', 'Age']
        self.staff_sort_filter = ttk.Combobox(filter_row2, values=staff_sort_options, state='readonly', width=12)
        self.staff_sort_filter.set('Overall Rating')
        self.staff_sort_filter.grid(row=0, column=5, padx=(0, 15), pady=2)
        self.staff_sort_filter.bind('<<ComboboxSelected>>', self.filter_staff)
        
        # Clear filters button
        ttk.Button(
            filter_row2,
            text="Clear Filters",
            style='Secondary.TButton',
            command=self.clear_staff_filters
        ).grid(row=0, column=6, padx=(15, 0), pady=2)
        
        # Results and selection info for staff
        info_frame = ttk.Frame(staff_tab, style='Panel.TFrame')
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.staff_results_label = ttk.Label(
            info_frame,
            text="Showing 0 staff",
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 10)
        )
        self.staff_results_label.pack(side=tk.LEFT)
        
        self.staff_selection_label = ttk.Label(
            info_frame,
            text="",
            style='Info.TLabel',
            font=(self.parent.FONT_FAMILY, 10)
        )
        self.staff_selection_label.pack(side=tk.RIGHT)
        
        # Enhanced staff list
        list_frame = ttk.Frame(staff_tab, style='Panel.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        staff_columns = {
            'name': ('Name', 180),
            'role': ('Role', 200),
            'dept': ('Department', 120),
            'ovr': ('Rating', 60),
            'experience': ('Experience', 100),
            'salary': ('Salary', 100),
            'years': ('Contract', 80),
            'age': ('Age', 50),
            'nationality': ('Country', 80)
        }
        
        self.fa_staff_tree = self.parent._create_treeview(list_frame, staff_columns, height=25)
        self.fa_staff_tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        self.fa_staff_tree.bind('<Button-3>', self.show_staff_context_menu)
        self.fa_staff_tree.bind('<Double-1>', self.negotiate_with_staff)
        self.fa_staff_tree.bind('<<TreeviewSelect>>', self.on_staff_selection_changed)
        
        # Action buttons for staff
        staff_actions = ttk.Frame(staff_tab, style='Panel.TFrame')
        staff_actions.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            staff_actions,
            text="Hire Selected Staff",
            style='Accent.TButton',
            command=self.hire_selected_staff
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            staff_actions,
            text="View Staff Profile",
            style='TButton',
            command=self.view_selected_staff_profile
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            staff_actions,
            text="Compare Staff",
            style='TButton',
            command=self.compare_selected_staff
        ).pack(side=tk.LEFT, padx=(0, 10))
    
    def create_market_overview_tab(self):
        """Create a market overview tab with analytics and trends."""
        overview_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        self.notebook.add(overview_tab, text="Market Overview")
        
        # Market summary section
        summary_frame = ttk.LabelFrame(overview_tab, text="Market Summary", padding=15)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create grid for market stats
        stats_grid = ttk.Frame(summary_frame, style='Panel.TFrame')
        stats_grid.pack(fill=tk.X)
        
        # Player market stats
        player_stats_frame = ttk.Frame(stats_grid, style='Panel.TFrame', padding=10)
        player_stats_frame.grid(row=0, column=0, sticky='ew', padx=5)
        stats_grid.columnconfigure(0, weight=1)
        
        ttk.Label(player_stats_frame, text="PLAYER MARKET", style='SubTitle.TLabel', 
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(anchor='w')
        
        # Calculate and display player market stats
        self.populate_player_market_stats(player_stats_frame)
        
        # Staff market stats
        staff_stats_frame = ttk.Frame(stats_grid, style='Panel.TFrame', padding=10)
        staff_stats_frame.grid(row=0, column=1, sticky='ew', padx=5)
        stats_grid.columnconfigure(1, weight=1)
        
        ttk.Label(staff_stats_frame, text="STAFF MARKET", style='SubTitle.TLabel',
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(anchor='w')
        
        # Calculate and display staff market stats
        self.populate_staff_market_stats(staff_stats_frame)
        
        # Top players section
        top_players_frame = ttk.LabelFrame(overview_tab, text="Top Available Players", padding=15)
        top_players_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create columns for top players by position
        positions_frame = ttk.Frame(top_players_frame, style='Panel.TFrame')
        positions_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add position-specific top player lists
        positions = [('Forwards', ['C', 'LW', 'RW']), ('Defense', ['LD', 'RD', 'D']), ('Goalies', ['G'])]
        
        for i, (pos_name, pos_types) in enumerate(positions):
            pos_frame = ttk.Frame(positions_frame, style='Panel.TFrame', padding=10)
            pos_frame.grid(row=0, column=i, sticky='nsew', padx=5)
            positions_frame.columnconfigure(i, weight=1)
            
            ttk.Label(pos_frame, text=pos_name.upper(), style='SubTitle.TLabel',
                     font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
            
            # Populate top players for this position group
            self.populate_top_players_by_position(pos_frame, pos_types)
    
    def populate_player_market_stats(self, parent_frame):
        """Populate player market statistics."""
        # Get free agent players
        free_agents = self.parent.game_manager.free_agents
        
        if not free_agents:
            ttk.Label(parent_frame, text="No free agents available", 
                     style='Info.TLabel').pack(anchor='w', pady=5)
            return
        
        # Calculate stats
        total_players = len(free_agents)
        avg_age = sum(p.age for p in free_agents) / total_players
        avg_rating = sum(p.overall_rating() for p in free_agents) / total_players
        
        # Position breakdown
        pos_counts = {}
        for player in free_agents:
            pos = player.primary_position.value
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        
        # Salary expectations (simplified calculation)
        avg_salary = sum(self.calculate_market_value(p) for p in free_agents) / total_players
        
        # Display stats
        stats_text = [
            f"Total Available: {total_players}",
            f"Average Age: {avg_age:.1f}",
            f"Average Rating: {avg_rating:.1f}",
            f"Avg. Market Value: ${avg_salary:,.0f}"
        ]
        
        for stat in stats_text:
            ttk.Label(parent_frame, text=stat, style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Position breakdown
        ttk.Label(parent_frame, text="By Position:", style='Info.TLabel',
                 font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        for pos, count in sorted(pos_counts.items()):
            ttk.Label(parent_frame, text=f"  {pos}: {count}",
                     style='Info.TLabel').pack(anchor='w', pady=1)
    
    def populate_staff_market_stats(self, parent_frame):
        """Populate staff market statistics."""
        # Get available staff
        available_staff = self.parent.game_manager.league.free_agent_staff
        
        if not available_staff:
            ttk.Label(parent_frame, text="No staff available", 
                     style='Info.TLabel').pack(anchor='w', pady=5)
            return
        
        # Calculate stats
        total_staff = len(available_staff)
        avg_age = sum(s.age for s in available_staff) / total_staff
        
        # Handle overall rating more defensively
        staff_ratings = []
        for s in available_staff:
            try:
                if hasattr(s, 'overall_rating') and callable(getattr(s, 'overall_rating')):
                    staff_ratings.append(s.overall_rating())
                elif hasattr(s, 'overall_rating'):
                    staff_ratings.append(s.overall_rating)
                else:
                    # Fallback to a simple average of key attributes
                    attrs = ['tactical_knowledge', 'man_management', 'motivating']
                    available_attrs = [getattr(s, attr, 10) for attr in attrs if hasattr(s, attr)]
                    if available_attrs:
                        staff_ratings.append(sum(available_attrs) / len(available_attrs))
                    else:
                        staff_ratings.append(10)  # Default rating
            except:
                staff_ratings.append(10)  # Default if calculation fails
        
        avg_rating = sum(staff_ratings) / len(staff_ratings) if staff_ratings else 10
        
        # Role breakdown
        role_counts = {}
        for staff in available_staff:
            role = staff.role.value
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Salary expectations
        avg_salary = sum(getattr(s, 'salary', 100000) for s in available_staff) / total_staff
        
        # Display stats
        stats_text = [
            f"Total Available: {total_staff}",
            f"Average Age: {avg_age:.1f}",
            f"Average Rating: {avg_rating:.1f}",
            f"Avg. Salary: ${avg_salary:,.0f}"
        ]
        
        for stat in stats_text:
            ttk.Label(parent_frame, text=stat, style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Role breakdown
        ttk.Label(parent_frame, text="By Role:", style='Info.TLabel',
                 font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        for role, count in sorted(role_counts.items()):
            role_display = role.replace('_', ' ').title()
            ttk.Label(parent_frame, text=f"  {role_display}: {count}",
                     style='Info.TLabel').pack(anchor='w', pady=1)
    
    def populate_top_players_by_position(self, parent_frame, positions):
        """Populate top players for specific positions."""
        # Get players for these positions
        position_players = [p for p in self.parent.game_manager.free_agents 
                          if p.primary_position.value in positions]
        
        if not position_players:
            ttk.Label(parent_frame, text="No players available", 
                     style='Info.TLabel').pack(anchor='w', pady=5)
            return
        
        # Sort by overall rating and take top 5
        top_players = sorted(position_players, key=lambda p: p.overall_rating(), reverse=True)[:5]
        
        # Create a small treeview for top players
        columns = {'name': ('Player', 120), 'ovr': ('OVR', 40), 'age': ('Age', 40)}
        
        top_tree = ttk.Treeview(parent_frame, columns=list(columns.keys()), 
                               show='headings', height=6)
        
        for col, (text, width) in columns.items():
            top_tree.heading(col, text=text)
            top_tree.column(col, width=width, anchor='center' if col != 'name' else 'w')
        
        # Populate with top players
        for player in top_players:
            values = [
                player.full_name,
                player.overall_rating(),
                player.age
            ]
            top_tree.insert('', 'end', values=values)
        
        top_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Bind double-click to open negotiations
        top_tree.bind('<Double-1>', lambda e: self.handle_market_overview_double_click(e, top_tree))
    
    def handle_market_overview_double_click(self, event, tree):
        """Handle double-click on market overview player."""
        item_id = tree.identify_row(event.y)
        if item_id:
            # Get player name from the tree
            player_name = tree.item(item_id, 'values')[0]
            
            # Find the actual player object
            for player in self.parent.game_manager.available_players:
                if player.full_name == player_name:
                    self.parent.open_contract_negotiation_window(player)
                    break
    
    def calculate_market_value(self, player):
        """Calculate market value for a player."""
        # Simple market value calculation based on overall rating and age
        base_value = player.overall_rating() * 50000
        
        # Age modifier
        if player.age <= 25:
            age_modifier = 1.2
        elif player.age <= 30:
            age_modifier = 1.0
        else:
            age_modifier = max(0.7, 1.0 - (player.age - 30) * 0.05)
        
        return int(base_value * age_modifier)
    
    def create_action_footer(self, parent):
        """Create the action buttons footer."""
        footer_frame = ttk.Frame(parent, style='Panel.TFrame', padding=(0, 15, 0, 0))
        footer_frame.pack(fill=tk.X)
        
        # Left side - bulk actions
        bulk_frame = ttk.Frame(footer_frame, style='Panel.TFrame')
        bulk_frame.pack(side=tk.LEFT)
        
        ttk.Button(
            bulk_frame,
            text="Refresh Market",
            style='TButton',
            command=self.refresh_market
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(
            bulk_frame,
            text="Export List",
            style='TButton',
            command=self.export_free_agents
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Right side - window controls
        control_frame = ttk.Frame(footer_frame, style='Panel.TFrame')
        control_frame.pack(side=tk.RIGHT)
        
        ttk.Button(
            control_frame,
            text="Help",
            style='Secondary.TButton',
            command=self.show_help
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            control_frame,
            text="Close",
            style='Secondary.TButton',
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=(10, 0))
    
    def setup_styles(self):
        """Setup custom styles for the free agency window."""
        style = ttk.Style()
        
        # Modern notebook style
        style.configure('Modern.TNotebook', 
                       tabposition='n',
                       background=self.parent.BG_COLOR)
        style.configure('Modern.TNotebook.Tab',
                       padding=[20, 10],
                       font=(self.parent.FONT_FAMILY, 11, 'bold'))
    
    def filter_players(self, event=None):
        """Filter the player list based on current filter settings."""
        self.populate_filtered_players()
    
    def filter_staff(self, event=None):
        """Filter the staff list based on current filter settings.""" 
        self.populate_filtered_staff()
    
    def populate_filtered_players(self):
        """Populate the player tree with filtered results."""
        # Clear existing items
        for item in self.fa_player_tree.get_children():
            self.fa_player_tree.delete(item)
        
        # Get filter values
        name_filter = self.player_name_search.get().lower()
        position_filter = self.player_position_filter.get()
        age_filter = self.player_age_filter.get()
        rating_filter = self.player_rating_filter.get()
        salary_filter = self.player_salary_filter.get()
        contract_filter = self.player_contract_filter.get()
        sort_by = self.player_sort_filter.get()
        
        # Filter players
        filtered_players = []
        for player in self.parent.game_manager.free_agents:
            # Name filter
            if name_filter and name_filter not in player.full_name.lower():
                continue
            
            # Position filter
            if position_filter != 'All' and player.primary_position.value != position_filter:
                continue
            
            # Age filter
            if age_filter != 'All':
                age = player.age
                if age_filter == '18-22' and not (18 <= age <= 22):
                    continue
                elif age_filter == '23-26' and not (23 <= age <= 26):
                    continue
                elif age_filter == '27-30' and not (27 <= age <= 30):
                    continue
                elif age_filter == '31-35' and not (31 <= age <= 35):
                    continue
                elif age_filter == '36+' and age < 36:
                    continue
            
            # Rating filter
            if rating_filter != 'All':
                rating = player.overall_rating()
                if rating_filter == '85+' and rating < 85:
                    continue
                elif rating_filter == '80-84' and not (80 <= rating <= 84):
                    continue
                elif rating_filter == '75-79' and not (75 <= rating <= 79):
                    continue
                elif rating_filter == '70-74' and not (70 <= rating <= 74):
                    continue
                elif rating_filter == '65-69' and not (65 <= rating <= 69):
                    continue
                elif rating_filter == '60-64' and not (60 <= rating <= 64):
                    continue
                elif rating_filter == '<60' and rating >= 60:
                    continue
            
            filtered_players.append(player)
        
        # Sort players
        if sort_by == 'Overall Rating':
            filtered_players.sort(key=lambda p: p.overall_rating(), reverse=True)
        elif sort_by == 'Age':
            filtered_players.sort(key=lambda p: p.age)
        elif sort_by == 'Name':
            filtered_players.sort(key=lambda p: p.full_name)
        elif sort_by == 'Position':
            filtered_players.sort(key=lambda p: p.primary_position.value)
        
        # Populate tree
        for player in filtered_players:
            salary = getattr(player, "salary", getattr(player.contract, "salary", 750000))
            contract_years = getattr(player, "contract_years", getattr(player.contract, "years_remaining", 1))
            
            values = [
                player.full_name,
                player.primary_position.value,
                player.age,
                player.overall_rating(),
                player.potential_grade,
                f"${salary:,}",
                f"{contract_years}y",
                getattr(player, 'nationality', 'Unknown'),
                getattr(player, 'shoots', 'R'),
                f"{getattr(player, 'height_feet', 6)}'{getattr(player, 'height_inches', 0)}\"",
                f"{getattr(player, 'weight', 180)} lbs"
            ]
            
            item_id = self.fa_player_tree.insert('', 'end', values=values)
            
            # Store player reference
            if 'fa_players' not in self.parent.tree_maps:
                self.parent.tree_maps['fa_players'] = {}
            self.parent.tree_maps['fa_players'][item_id] = player
        
        # Update results label
        self.player_results_label.config(text=f"Showing {len(filtered_players)} players")
    
    def populate_filtered_staff(self):
        """Populate the staff tree with filtered results."""
        # Clear existing items
        for item in self.fa_staff_tree.get_children():
            self.fa_staff_tree.delete(item)
        
        # Get filter values
        name_filter = self.staff_name_search.get().lower()
        role_filter = self.staff_role_filter.get()
        department_filter = self.staff_department_filter.get()
        experience_filter = self.staff_experience_filter.get()
        salary_filter = self.staff_salary_filter.get()
        sort_by = self.staff_sort_filter.get()
        
        # Filter staff
        filtered_staff = []
        for staff in self.parent.league.free_agent_staff:
            # Name filter
            if name_filter and name_filter not in staff.full_name.lower():
                continue
            
            # Role filter
            if role_filter != 'All' and staff.role.value != role_filter:
                continue
            
            # Department filter
            if department_filter != 'All':
                from game_classes import Staff as StaffClass
                staff_dept = StaffClass.get_role_department(staff.role)
                if staff_dept != department_filter:
                    continue
            
            filtered_staff.append(staff)
        
        # Sort staff
        if sort_by == 'Overall Rating':
            filtered_staff.sort(key=lambda s: s.overall_rating, reverse=True)
        elif sort_by == 'Name':
            filtered_staff.sort(key=lambda s: s.full_name)
        elif sort_by == 'Role':
            filtered_staff.sort(key=lambda s: s.role.value)
        elif sort_by == 'Age':
            filtered_staff.sort(key=lambda s: s.age)
        
        # Populate tree
        for staff in filtered_staff:
            from game_classes import Staff as StaffClass
            department = StaffClass.get_role_department(staff.role)
            experience = max(0, staff.age - 25)
            
            values = [
                staff.full_name,
                staff.role.value,
                department,
                staff.overall_rating,
                f"{experience}y",
                f"${staff.salary:,}",
                f"{staff.contract_years}y",
                staff.age,
                staff.nationality
            ]
            
            item_id = self.fa_staff_tree.insert('', 'end', values=values)
            
            # Store staff reference
            if 'fa_staff' not in self.parent.tree_maps:
                self.parent.tree_maps['fa_staff'] = {}
            self.parent.tree_maps['fa_staff'][item_id] = staff
        
        # Update results label
        self.staff_results_label.config(text=f"Showing {len(filtered_staff)} staff")
    
    def clear_player_filters(self):
        """Clear all player filters."""
        self.player_name_search.delete(0, tk.END)
        self.player_position_filter.set('All')
        self.player_age_filter.set('All')
        self.player_rating_filter.set('All')
        self.player_salary_filter.set('All')
        self.player_contract_filter.set('All')
        self.player_sort_filter.set('Overall Rating')
        self.populate_filtered_players()
    
    def clear_staff_filters(self):
        """Clear all staff filters."""
        self.staff_name_search.delete(0, tk.END)
        self.staff_role_filter.set('All')
        self.staff_department_filter.set('All')
        self.staff_experience_filter.set('All')
        self.staff_salary_filter.set('All')
        self.staff_sort_filter.set('Overall Rating')
        self.populate_filtered_staff()
    
    def on_player_selection_changed(self, event=None):
        """Handle player selection changes."""
        selection = self.fa_player_tree.selection()
        if selection:
            self.player_selection_label.config(text=f"{len(selection)} player(s) selected")
        else:
            self.player_selection_label.config(text="")
    
    def on_staff_selection_changed(self, event=None):
        """Handle staff selection changes."""
        selection = self.fa_staff_tree.selection()
        if selection:
            self.staff_selection_label.config(text=f"{len(selection)} staff selected")
        else:
            self.staff_selection_label.config(text="")
    
    def sign_selected_player(self):
        """Sign the selected player."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to sign.")
            return
        
        player = self.parent.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.parent.open_contract_negotiation_window(player)
    
    def hire_selected_staff(self):
        """Hire the selected staff member."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a staff member to hire.")
            return
        
        staff = self.parent.tree_maps.get('fa_staff', {}).get(selection[0])
        if staff:
            # Implement staff hiring logic here
            tk.messagebox.showinfo("Staff Hired", f"{staff.full_name} has been hired!")
    
    def view_selected_player_profile(self):
        """View the selected player's profile."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to view.")
            return
        
        player = self.parent.tree_maps.get('fa_players', {}).get(selection[0])
        if player:
            self.parent.open_player_profile(player)
    
    def view_selected_staff_profile(self):
        """View the selected staff member's profile."""
        selection = self.fa_staff_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a staff member to view.")
            return
        
        # Implement staff profile viewing
        tk.messagebox.showinfo("Staff Profile", "Staff profile viewing coming soon!")
    
    def negotiate_with_player(self, event=None):
        """Negotiate with a player (double-click handler)."""
        self.sign_selected_player()
    
    def negotiate_with_staff(self, event=None):
        """Negotiate with a staff member (double-click handler)."""
        self.hire_selected_staff()
    
    def _show_free_agency_context_menu(self, event):
        """Show context menu for free agency-specific options"""
        if hasattr(self, 'fa_player_tree'):
            selection = self.fa_player_tree.selection()
            if selection:
                player = self.parent.tree_maps.get(self.fa_player_tree, {}).get(selection[0])
                if player:
                    # Create context menu with free agency options
                    context_menu = PlayerContextMenu(self)
                    context_menu.add_separator()
                    context_menu.add_command(f"Sign {player.full_name}", lambda p=player: self.sign_selected_player())
                    context_menu.add_command("Market Analysis", lambda p=player: self.show_player_market_analysis())
                    context_menu.add_command("Compare Offers", lambda p=player: self._compare_offers(p))
                    context_menu.show_context_menu(event, player)
    
    def show_staff_context_menu(self, event):
        """Show context menu for staff."""
        item_id = self.fa_staff_tree.identify_row(event.y)
        if not item_id:
            return
        
        self.fa_staff_tree.selection_set(item_id)
        staff = self.parent.tree_maps.get('fa_staff', {}).get(item_id)
        if not staff:
            return
        
        menu = tk.Menu(self, tearoff=0, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        menu.add_command(label=f"Hire {staff.full_name}", command=self.hire_selected_staff)
        menu.add_command(label="View Staff Profile", command=self.view_selected_staff_profile)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def compare_selected_players(self):
        """Compare selected players."""
        selection = self.fa_player_tree.selection()
        if len(selection) < 2:
            tk.messagebox.showwarning("Selection Required", 
                                    "Please select 2-4 players to compare.")
            return
        
        if len(selection) > 4:
            tk.messagebox.showwarning("Too Many Selected", 
                                    "Please select no more than 4 players to compare.")
            return
        
        # Get selected players
        selected_players = []
        for item_id in selection:
            if item_id in self.parent.tree_maps.get('fa_players', {}):
                player = self.parent.tree_maps['fa_players'][item_id]
                selected_players.append(player)
        
        if len(selected_players) < 2:
            tk.messagebox.showwarning("Invalid Selection", 
                                    "Could not find selected players for comparison.")
            return
        
        # Create comparison window
        self.create_player_comparison_window(selected_players)
    
    def create_player_comparison_window(self, players):
        """Create a detailed player comparison window."""
        comparison_window = tk.Toplevel(self)
        comparison_window.title("Player Comparison")
        comparison_window.configure(background=self.parent.BG_COLOR)
        comparison_window.geometry("1000x700")
        
        # Main container
        main_frame = ttk.Frame(comparison_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Player Comparison", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create scrollable frame
        canvas = tk.Canvas(main_frame, background=self.parent.BG_COLOR)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Comparison table
        self.create_comparison_table(scrollable_frame, players)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", 
                              command=comparison_window.destroy)
        close_btn.pack(pady=10)
    
    def create_comparison_table(self, parent, players):
        """Create the detailed comparison table."""
        # Headers
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=5)
        
        ttk.Label(header_frame, text="Attribute", style='Header.TLabel', 
                 width=20).grid(row=0, column=0, padx=5, sticky='w')
        
        for i, player in enumerate(players):
            ttk.Label(header_frame, text=player.full_name, style='Header.TLabel',
                     width=15).grid(row=0, column=i+1, padx=5)
        
        # Basic Info Section
        self.add_comparison_section(parent, "Basic Information", [
            ("Age", lambda p: str(p.age)),
            ("Position", lambda p: str(p.primary_position)),
            ("Overall Rating", lambda p: str(p.overall_rating())),
            ("Team", lambda p: getattr(p, 'team_name', 'Free Agent')),
        ], players)
        
        # Contract Info Section
        self.add_comparison_section(parent, "Contract Information", [
            ("Salary", lambda p: f"${getattr(p.contract, 'salary', 750000):,}" if p.contract else "No Contract"),
            ("Years Left", lambda p: str(getattr(p.contract, 'years_remaining', 0)) if p.contract else "0"),
            ("Contract Type", lambda p: getattr(p.contract, 'contract_type', 'None') if p.contract else "None"),
        ], players)
        
        # Performance Stats Section
        self.add_comparison_section(parent, "Performance Stats", [
            ("Games Played", lambda p: str(getattr(p, 'games_played', 0))),
            ("Goals", lambda p: str(getattr(p, 'goals', 0))),
            ("Assists", lambda p: str(getattr(p, 'assists', 0))),
            ("Points", lambda p: str(getattr(p, 'points', 0))),
            ("+/-", lambda p: f"+{getattr(p, 'plus_minus', 0)}" if getattr(p, 'plus_minus', 0) >= 0 else str(getattr(p, 'plus_minus', 0))),
        ], players)
        
        # Key Attributes Section  
        self.add_comparison_section(parent, "Key Attributes", [
            ("Skating", lambda p: str(getattr(p, 'skating', 10))),
            ("Shooting", lambda p: str(getattr(p, 'shooting', 10))),
            ("Passing", lambda p: str(getattr(p, 'passing', 10))),
            ("Checking", lambda p: str(getattr(p, 'checking', 10))),
            ("Hockey IQ", lambda p: str(getattr(p, 'hockey_iq', 10))),
            ("Determination", lambda p: str(getattr(p, 'determination', 10))),
        ], players)
    
    def add_comparison_section(self, parent, section_title, attributes, players):
        """Add a section to the comparison table."""
        # Section header
        section_frame = ttk.Frame(parent)
        section_frame.pack(fill='x', pady=10)
        
        ttk.Label(section_frame, text=section_title, style='Title.TLabel').pack(anchor='w')
        
        # Attribute rows
        for row_idx, (attr_name, attr_func) in enumerate(attributes):
            row_frame = ttk.Frame(section_frame)
            row_frame.pack(fill='x', pady=2)
            
            # Attribute name
            ttk.Label(row_frame, text=attr_name, width=20).grid(row=0, column=0, padx=5, sticky='w')
            
            # Player values
            values = []
            for player in players:
                try:
                    value = attr_func(player)
                    values.append(value)
                except:
                    values.append("N/A")
            
            # Highlight best/worst values for numeric attributes
            if attr_name in ["Overall Rating", "Age", "Goals", "Assists", "Points", "Skating", "Shooting", "Passing", "Checking", "Hockey IQ", "Determination"]:
                try:
                    numeric_values = [int(v) for v in values if v != "N/A" and v.replace('-', '').replace('+', '').isdigit()]
                    if numeric_values:
                        best_val = max(numeric_values) if attr_name != "Age" else min(numeric_values)
                        worst_val = min(numeric_values) if attr_name != "Age" else max(numeric_values)
                        
                        for i, value in enumerate(values):
                            try:
                                val_int = int(value.replace('-', '').replace('+', ''))
                                if val_int == best_val:
                                    label = ttk.Label(row_frame, text=value, foreground='green', width=15)
                                elif val_int == worst_val and len(set(numeric_values)) > 1:
                                    label = ttk.Label(row_frame, text=value, foreground='red', width=15)
                                else:
                                    label = ttk.Label(row_frame, text=value, width=15)
                            except:
                                label = ttk.Label(row_frame, text=value, width=15)
                            label.grid(row=0, column=i+1, padx=5)
                    else:
                        for i, value in enumerate(values):
                            ttk.Label(row_frame, text=value, width=15).grid(row=0, column=i+1, padx=5)
                except:
                    for i, value in enumerate(values):
                        ttk.Label(row_frame, text=value, width=15).grid(row=0, column=i+1, padx=5)
            else:
                for i, value in enumerate(values):
                    ttk.Label(row_frame, text=value, width=15).grid(row=0, column=i+1, padx=5)
    
    def compare_selected_staff(self):
        """Compare selected staff."""
        tk.messagebox.showinfo("Staff Comparison", "Staff comparison feature coming soon!")
    
    def show_player_market_analysis(self):
        """Show market analysis for the selected player."""
        selection = self.fa_player_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to analyze.")
            return
        
        # Get selected player
        item_id = selection[0]
        if item_id not in self.parent.tree_maps.get('fa_players', {}):
            tk.messagebox.showerror("Error", "Could not find selected player.")
            return
        
        player = self.parent.tree_maps['fa_players'][item_id]
        self.create_market_analysis_window(player)
    
    def create_market_analysis_window(self, player):
        """Create market analysis window for a player."""
        analysis_window = tk.Toplevel(self)
        analysis_window.title(f"Market Analysis - {player.full_name}")
        analysis_window.configure(background=self.parent.BG_COLOR)
        analysis_window.geometry("800x600")
        
        # Main container
        main_frame = ttk.Frame(analysis_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"Market Analysis: {player.full_name}", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create notebook for different analysis tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)
        
        # Market Value Tab
        value_frame = ttk.Frame(notebook)
        notebook.add(value_frame, text="Market Value")
        self.create_value_analysis(value_frame, player)
        
        # Comparable Players Tab
        comp_frame = ttk.Frame(notebook)
        notebook.add(comp_frame, text="Comparable Players")
        self.create_comparable_analysis(comp_frame, player)
        
        # Contract Projection Tab
        contract_frame = ttk.Frame(notebook)
        notebook.add(contract_frame, text="Contract Projection")
        self.create_contract_projection(contract_frame, player)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", 
                              command=analysis_window.destroy)
        close_btn.pack(pady=10)
    
    def create_value_analysis(self, parent, player):
        """Create market value analysis."""
        # Player info section
        info_frame = ttk.LabelFrame(parent, text="Player Information")
        info_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(info_frame, text=f"Age: {player.age}").pack(anchor='w', padx=10, pady=2)
        ttk.Label(info_frame, text=f"Position: {player.primary_position}").pack(anchor='w', padx=10, pady=2)
        ttk.Label(info_frame, text=f"Overall Rating: {player.overall_rating()}").pack(anchor='w', padx=10, pady=2)
        
        # Market value calculation
        value_frame = ttk.LabelFrame(parent, text="Estimated Market Value")
        value_frame.pack(fill='x', padx=10, pady=10)
        
        # Calculate estimated market value based on overall rating and age
        base_value = self.calculate_market_value(player)
        
        ttk.Label(value_frame, text=f"Estimated Annual Value: ${base_value:,}").pack(anchor='w', padx=10, pady=2)
        ttk.Label(value_frame, text=f"Suggested Contract Length: {self.suggest_contract_length(player)} years").pack(anchor='w', padx=10, pady=2)
        
        # Value factors
        factors_frame = ttk.LabelFrame(parent, text="Value Factors")
        factors_frame.pack(fill='x', padx=10, pady=10)
        
        factors = self.get_value_factors(player)
        for factor in factors:
            ttk.Label(factors_frame, text=f"• {factor}").pack(anchor='w', padx=10, pady=1)
    
    def create_comparable_analysis(self, parent, player):
        """Create comparable players analysis."""
        comp_frame = ttk.LabelFrame(parent, text="Similar Players")
        comp_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Find comparable players
        comparables = self.find_comparable_players(player)
        
        if comparables:
            # Create treeview for comparables
            columns = ('Name', 'Age', 'Position', 'Overall', 'Team', 'Salary')
            tree = ttk.Treeview(comp_frame, columns=columns, show='headings', height=10)
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)
            
            for comp_player in comparables:
                salary = getattr(comp_player.contract, 'salary', 'No Contract') if comp_player.contract else 'Free Agent'
                if isinstance(salary, int):
                    salary_str = f"${salary:,}"
                else:
                    salary_str = str(salary)
                    
                tree.insert('', 'end', values=(
                    comp_player.full_name,
                    comp_player.age,
                    str(comp_player.primary_position),
                    comp_player.overall_rating(),
                    getattr(comp_player, 'team_name', 'Free Agent'),
                    salary_str
                ))
            
            tree.pack(fill='both', expand=True, padx=10, pady=10)
        else:
            ttk.Label(comp_frame, text="No comparable players found.").pack(pady=20)
    
    def create_contract_projection(self, parent, player):
        """Create contract projection analysis."""
        proj_frame = ttk.LabelFrame(parent, text="Contract Recommendations")
        proj_frame.pack(fill='x', padx=10, pady=10)
        
        # Calculate different contract scenarios
        market_value = self.calculate_market_value(player)
        
        # Short-term deal
        short_term = ttk.Frame(proj_frame)
        short_term.pack(fill='x', padx=10, pady=5)
        ttk.Label(short_term, text="Short-term (1-2 years):", font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        ttk.Label(short_term, text=f"  ${market_value * 1.1:,.0f} AAV - Prove-it deal").pack(anchor='w')
        
        # Medium-term deal
        medium_term = ttk.Frame(proj_frame)
        medium_term.pack(fill='x', padx=10, pady=5)
        ttk.Label(medium_term, text="Medium-term (3-4 years):", font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        ttk.Label(medium_term, text=f"  ${market_value:,.0f} AAV - Fair market value").pack(anchor='w')
        
        # Long-term deal
        long_term = ttk.Frame(proj_frame)
        long_term.pack(fill='x', padx=10, pady=5)
        ttk.Label(long_term, text="Long-term (5+ years):", font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        ttk.Label(long_term, text=f"  ${market_value * 0.9:,.0f} AAV - Security discount").pack(anchor='w')
    
    def calculate_market_value(self, player):
        """Calculate estimated market value for a player."""
        base_value = 750000  # League minimum
        
        # Overall rating multiplier
        rating_multiplier = max(1.0, player.overall_rating() / 75.0)
        base_value *= rating_multiplier
        
        # Age adjustments
        if player.age < 25:  # Young player premium
            base_value *= 1.2
        elif player.age > 32:  # Veteran discount
            base_value *= 0.8
        
        # Position adjustments
        position_str = str(player.primary_position).upper()
        if 'GOALIE' in position_str:
            base_value *= 1.5  # Goalies typically earn more
        elif 'CENTER' in position_str or 'DEFENCE' in position_str:
            base_value *= 1.1  # Premium positions
        
        # Performance bonuses
        goals = getattr(player, 'goals', 0)
        assists = getattr(player, 'assists', 0)
        if goals + assists > 50:
            base_value *= 1.3
        elif goals + assists > 30:
            base_value *= 1.15
        
        return int(base_value)
    
    def suggest_contract_length(self, player):
        """Suggest appropriate contract length."""
        if player.age < 25:
            return 3  # Bridge deal for young players
        elif player.age < 30:
            return 5  # Prime years
        elif player.age < 35:
            return 2  # Short term for aging players
        else:
            return 1  # Year by year for veterans
    
    def get_value_factors(self, player):
        """Get factors affecting player value."""
        factors = []
        
        if player.age < 25:
            factors.append("Young player with upside potential")
        elif player.age > 33:
            factors.append("Veteran experience but declining years")
        
        if player.overall_rating() > 85:
            factors.append("Elite talent commands premium")
        elif player.overall_rating() < 70:
            factors.append("Developing player or depth role")
        
        goals = getattr(player, 'goals', 0)
        if goals > 25:
            factors.append("Proven goal scorer")
        
        assists = getattr(player, 'assists', 0)
        if assists > 35:
            factors.append("Elite playmaker")
        
        if getattr(player, 'plus_minus', 0) > 15:
            factors.append("Strong defensive impact")
        
        return factors if factors else ["Standard market factors apply"]
    
    def find_comparable_players(self, target_player):
        """Find players comparable to the target player."""
        comparables = []
        target_rating = target_player.overall_rating()
        target_age = target_player.age
        target_position = str(target_player.primary_position)
        
        # Search through all teams for similar players
        for team in self.parent.league.teams:
            for roster_list in [team.roster, team.ahl_roster, team.prospects]:
                for player in roster_list:
                    if player == target_player:
                        continue
                    
                    # Check similarity criteria
                    rating_diff = abs(player.overall_rating() - target_rating)
                    age_diff = abs(player.age - target_age)
                    same_position = str(player.primary_position) == target_position
                    
                    # Include if similar rating, age, and position
                    if rating_diff <= 5 and age_diff <= 3 and same_position:
                        comparables.append(player)
        
        # Sort by overall rating
        comparables.sort(key=lambda p: p.overall_rating(), reverse=True)
        return comparables[:10]  # Return top 10 most similar
    
    def refresh_market(self):
        """Refresh the free agency market."""
        # Update all filtered views
        self.update_views()
        
        # Refresh the Market Overview tab by recreating it
        try:
            # Find and remove the existing Market Overview tab
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == "Market Overview":
                    # Get the tab widget and destroy it
                    tab_widget = self.notebook.nametowidget(self.notebook.tabs()[i])
                    self.notebook.forget(i)
                    tab_widget.destroy()
                    break
            
            # Recreate the Market Overview tab
            self.create_market_overview_tab()
            
        except (tk.TclError, IndexError):
            # If there's an error, just update views
            pass
        
        tk.messagebox.showinfo("Market Refreshed", "Free agency market has been refreshed!")
    
    def update_views(self):
        """Update all views with current data."""
        self.populate_filtered_players()
        self.populate_filtered_staff()
        
        # Also refresh market overview if the current tab is market overview
        try:
            current_tab = self.notebook.index(self.notebook.select())
            if self.notebook.tab(current_tab, "text") == "Market Overview":
                # Refresh market overview data by recreating the tab
                self.refresh_market_overview_data()
        except (tk.TclError, AttributeError):
            pass
    
    def refresh_market_overview_data(self):
        """Refresh just the data in the Market Overview tab without recreating it."""
        # This is a lighter refresh that just updates the data
        # For now, we'll use the full refresh method, but this could be optimized
        pass
    
    def export_free_agents(self):
        """Export the free agent lists."""
        tk.messagebox.showinfo("Export", "Export feature coming soon!")
    
    def show_help(self):
        """Show help information."""
        help_text = """
FREE AGENCY HELP

Use the filters to narrow down available players and staff:
• Name: Search by player/staff name
• Position/Role: Filter by specific positions or roles
• Age: Filter by age ranges
• Rating: Filter by overall rating ranges
• Salary: Filter by salary expectations

Double-click any player or staff member to begin negotiations.
Right-click for additional options and analysis tools.

The Market Overview tab provides analytics and top available talent.
        """
        tk.messagebox.showinfo("Free Agency Help", help_text)
    
    def _compare_offers(self, player):
        """Compare contract offers for the player"""
        messagebox.showinfo("Contract Offers", 
                          f"Contract comparison for {player.full_name}\n"
                          f"Your offer: Not submitted\n"
                          f"Competing offers: 2 other teams\n"
                          f"Recommended: Increase offer by 10%")

class TradeWindow(tk.Toplevel):
    """Modern Trade Center: live value meter, picks, AI counter-offers, history."""

    METER_W = 280
    METER_H = 22

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Trade Center")
        self.geometry("1280x760")
        self.configure(background=parent.BG_COLOR)
        self.trade_offers = {'user': [], 'partner': []}
        self._history_visible = False

        import trade_engine as te
        self.te = te
        gm = getattr(parent, 'game_manager', None)
        if gm is not None and not hasattr(gm, 'trade_history'):
            gm.trade_history = []

        # ---- Header ----
        header = ttk.Frame(self, style='Panel.TFrame', padding=(14, 10))
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(header, text="Trade Center",
                  font=(parent.FONT_FAMILY, 18, 'bold'),
                  style='Heading.TLabel').pack(side='left')
        ttk.Label(header, text="Build a deal both GMs can live with",
                  style='Secondary.TLabel').pack(side='left', padx=(12, 0))
        hist_btn = ttk.Button(header, text="Trade History",
                              command=self._toggle_history,
                              style='Secondary.TButton')
        hist_btn.pack(side='right')

        # Partner selector row
        partner_row = ttk.Frame(self, style='Panel.TFrame', padding=(14, 6))
        partner_row.pack(fill='x', padx=10)
        ttk.Label(partner_row, text="Trade partner:", style='TLabel').pack(side='left')
        partner_teams = sorted(t.team_name for t in parent.league.teams
                               if t != parent.user_team)
        self.partner_var = tk.StringVar(master=self)
        self.partner_combo = ttk.Combobox(partner_row, textvariable=self.partner_var,
                                          values=partner_teams, state='readonly', width=28)
        self.partner_combo.pack(side='left', padx=(8, 16))
        self.partner_combo.bind("<<ComboboxSelected>>", self.update_trade_partner_roster)
        if partner_teams:
            self.partner_var.set(partner_teams[0])
        ttk.Label(partner_row, text="Their needs:", style='Secondary.TLabel').pack(side='left')
        self.needs_label = ttk.Label(partner_row, text="", style='TLabel',
                                     font=(parent.FONT_FAMILY, 10, 'bold'))
        self.needs_label.pack(side='left', padx=(6, 0))

        # ---- Main 3-column layout ----
        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)
        self.main_pane = main_pane

        # Your roster
        user_frame = ttk.Frame(main_pane, style='Card.TFrame', padding=8)
        main_pane.add(user_frame, weight=2)
        ttk.Label(user_frame, text=parent.user_team.team_name,
                  font=(parent.FONT_FAMILY, 12, 'bold'),
                  style='Card.TLabel').pack(anchor='w', pady=(0, 4))
        self.user_trade_tree = parent._create_treeview(
            user_frame, {'name': ('Name', 150), 'ovr': ('OVR', 40)})
        self.user_trade_tree.pack(fill='both', expand=True)
        btn_row = ttk.Frame(user_frame, style='Card.TFrame')
        btn_row.pack(fill='x', pady=(6, 0))
        ttk.Button(btn_row, text="Add Player  →",
                   command=lambda: self._add_to_trade('user'),
                   style='Secondary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(btn_row, text="Add Pick",
                   command=lambda: self._add_pick_dialog('user'),
                   style='Secondary.TButton').pack(side='left')

        # Center: deal panel
        center = ttk.Frame(main_pane, style='Panel.TFrame', padding=10)
        main_pane.add(center, weight=1)

        ttk.Label(center, text="YOUR OFFER", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.user_offer_list = tk.Listbox(center, height=6, activestyle='none',
                                          bg='#232a3a', fg='#e8ecf4',
                                          selectbackground='#335577', relief='flat',
                                          highlightthickness=1, highlightbackground='#3a4a63')
        self.user_offer_list.pack(fill='x', pady=(2, 2))
        ttk.Button(center, text="Remove selected",
                   command=lambda: self._remove_from_trade('user'),
                   style='Secondary.TButton').pack(anchor='e', pady=(0, 8))

        # Live trade meter
        ttk.Label(center, text="TRADE METER", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.meter_canvas = tk.Canvas(center, width=self.METER_W, height=self.METER_H,
                                      highlightthickness=0, bg='#141a26')
        self.meter_canvas.pack(fill='x', pady=(2, 2))
        self.meter_label = ttk.Label(center, text="Add assets to evaluate",
                                     style='TLabel', font=(parent.FONT_FAMILY, 10, 'bold'))
        self.meter_label.pack(anchor='w', pady=(0, 2))
        self.cap_label = ttk.Label(center, text="", style='Secondary.TLabel',
                                   wraplength=300, justify='left')
        self.cap_label.pack(anchor='w', pady=(0, 8))

        ttk.Label(center, text="THEIR OFFER", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.partner_offer_list = tk.Listbox(center, height=6, activestyle='none',
                                             bg='#232a3a', fg='#e8ecf4',
                                             selectbackground='#335577', relief='flat',
                                             highlightthickness=1, highlightbackground='#3a4a63')
        self.partner_offer_list.pack(fill='x', pady=(2, 2))
        ttk.Button(center, text="Remove selected",
                   command=lambda: self._remove_from_trade('partner'),
                   style='Secondary.TButton').pack(anchor='e', pady=(0, 8))

        ttk.Button(center, text="Propose Trade", command=self.propose_trade,
                   style='TButton').pack(fill='x', pady=(6, 0))
        ttk.Label(center, text="The AI GM evaluates value, needs and cap space.\nLowball and expect a counter.",
                  style='Secondary.TLabel', wraplength=300, justify='center',
                  font=(parent.FONT_FAMILY, 9)).pack(pady=(8, 0))

        # Partner roster
        partner_frame = ttk.Frame(main_pane, style='Card.TFrame', padding=8)
        main_pane.add(partner_frame, weight=2)
        self.partner_title = ttk.Label(partner_frame, text="Trade Partner",
                                       font=(parent.FONT_FAMILY, 12, 'bold'),
                                       style='Card.TLabel')
        self.partner_title.pack(anchor='w', pady=(0, 4))
        self.partner_trade_tree = parent._create_treeview(
            partner_frame, {'name': ('Name', 150), 'ovr': ('OVR', 40)})
        self.partner_trade_tree.pack(fill='both', expand=True)
        pbtn_row = ttk.Frame(partner_frame, style='Card.TFrame')
        pbtn_row.pack(fill='x', pady=(6, 0))
        ttk.Button(pbtn_row, text="←  Add Player",
                   command=lambda: self._add_to_trade('partner'),
                   style='Secondary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(pbtn_row, text="Add Pick",
                   command=lambda: self._add_pick_dialog('partner'),
                   style='Secondary.TButton').pack(side='left')

        # History panel (hidden by default)
        self.history_frame = ttk.Frame(self, style='Panel.TFrame', padding=(14, 6))

        self.update_views()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def update_views(self):
        self.parent._populate_player_tree(self.user_trade_tree,
                                          self.parent.user_team.roster,
                                          trade_view=True)
        self.update_trade_partner_roster()
        self._refresh_offer_lists()
        self._update_meter()

    def update_trade_partner_roster(self, event=None):
        name = self.partner_var.get()
        team = next((t for t in self.parent.league.teams
                     if t.team_name == name), None)
        if team:
            self.partner_title.config(text=team.team_name)
            self.parent._populate_player_tree(self.partner_trade_tree,
                                              team.roster, trade_view=True)
            needs = self.te.team_needs(team)[:3]
            self.needs_label.config(text="  ".join(needs) if needs else "—")
        # Partner changed -> clear their side of the deal
        self.trade_offers['partner'] = []
        self._refresh_offer_lists()
        self._update_meter()

    def _refresh_offer_lists(self):
        for side, lb in (('user', self.user_offer_list),
                         ('partner', self.partner_offer_list)):
            lb.delete(0, tk.END)
            for a in self.trade_offers[side]:
                lb.insert(tk.END,
                          f"{self.te.asset_label(a)}  [{self.te.asset_value(a)}]")

    # ------------------------------------------------------------------
    # Trade meter
    # ------------------------------------------------------------------
    def _eval(self):
        return self.te.evaluate_trade(self.trade_offers['user'],
                                      self.trade_offers['partner'])

    def _update_meter(self):
        c = self.meter_canvas
        c.delete('all')
        w = c.winfo_width() or self.METER_W
        h = self.METER_H
        ev = self._eval()
        total = ev.user_value + ev.partner_value
        # Track
        c.create_rectangle(0, 0, w, h, fill='#232a3a', outline='')
        if total > 0:
            uw = w * ev.user_value / total
            c.create_rectangle(0, 0, uw, h, fill='#4a9eff', outline='')
            c.create_rectangle(uw, 0, w, h, fill='#e8b93c', outline='')
            # Center marker
            c.create_line(w/2, 0, w/2, h, fill='#0e1420', width=2)
        # Label
        if not self.trade_offers['user'] or not self.trade_offers['partner']:
            self.meter_label.config(text="Add assets on both sides to evaluate",
                                    foreground='#7a8aa3')
        else:
            color = {'Fair deal': '#46c93a', 'You overpay': '#4a9eff',
                     'They overpay': '#e8b93c'}.get(ev.label, '#e8ecf4')
            self.meter_label.config(
                text=f"{ev.label}  (you {ev.user_value} vs them {ev.partner_value})",
                foreground=color)
        # Cap impact for the user
        gm_team = self.parent.user_team
        in_sal = sum(getattr(p, 'salary', 0) or 0 for p in self.trade_offers['partner']
                     if not self.te._is_pick(p))
        out_sal = sum(getattr(p, 'salary', 0) or 0 for p in self.trade_offers['user']
                      if not self.te._is_pick(p))
        try:
            new_pay = gm_team.payroll - out_sal + in_sal
            room = gm_team.salary_cap - new_pay
            ok = room >= 0
            self.cap_label.config(
                text=f"Cap room after: ${room/1e6:.1f}M"
                     if ok else f"OVER CAP by ${-room/1e6:.1f}M — shed salary!",
                foreground='#46c93a' if ok else '#e74c3c')
        except Exception:
            self.cap_label.config(text="")

    # ------------------------------------------------------------------
    # Building the deal
    # ------------------------------------------------------------------
    def _add_to_trade(self, side):
        tree = self.user_trade_tree if side == 'user' else self.partner_trade_tree
        tree_map = self.parent.tree_maps.get(tree, {})
        sel = tree.selection()
        if not sel:
            return
        player = tree_map.get(sel[0])
        if player and player not in self.trade_offers[side]:
            self.trade_offers[side].append(player)
            self._refresh_offer_lists()
            self._update_meter()

    def _remove_from_trade(self, side):
        lb = self.user_offer_list if side == 'user' else self.partner_offer_list
        sel = lb.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.trade_offers[side][idx]
        self._refresh_offer_lists()
        self._update_meter()

    def _team_picks(self, team):
        picks = []
        for yr in sorted(getattr(team, 'draft_picks', {}).keys()):
            for pk in team.draft_picks[yr]:
                if getattr(pk, 'current_team', '') == team.team_name:
                    picks.append(pk)
        return picks

    def _add_pick_dialog(self, side):
        team = (self.parent.user_team if side == 'user' else
                next((t for t in self.parent.league.teams
                      if t.team_name == self.partner_var.get()), None))
        if team is None:
            return
        picks = [p for p in self._team_picks(team)
                 if p not in self.trade_offers[side]]
        if not picks:
            messagebox.showinfo("No picks", f"{team.team_name} has no tradeable picks.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add draft pick")
        dlg.geometry("420x320")
        dlg.configure(background=self.parent.BG_COLOR)
        dlg.transient(self)
        ttk.Label(dlg, text=f"Select a {team.team_name} pick:",
                  style='TLabel', font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(pady=10)
        lb = tk.Listbox(dlg, height=12, bg='#232a3a', fg='#e8ecf4',
                        selectbackground='#335577', relief='flat')
        lb.pack(fill='both', expand=True, padx=12)
        for pk in picks:
            lb.insert(tk.END, f"{self.te.asset_label(pk)}  [{self.te.asset_value(pk)}]")
        def add():
            sel = lb.curselection()
            if sel:
                self.trade_offers[side].append(picks[sel[0]])
                self._refresh_offer_lists()
                self._update_meter()
                dlg.destroy()
        ttk.Button(dlg, text="Add to Offer", command=add,
                   style='TButton').pack(pady=10)

    # ------------------------------------------------------------------
    # Proposing + AI negotiation
    # ------------------------------------------------------------------
    def _partner_team(self):
        return next((t for t in self.parent.league.teams
                     if t.team_name == self.partner_var.get()), None)

    def propose_trade(self):
        partner = self._partner_team()
        if partner is None:
            messagebox.showwarning("No partner", "Select a trade partner first.")
            return
        user_assets = list(self.trade_offers['user'])
        partner_assets = list(self.trade_offers['partner'])
        if not user_assets or not partner_assets:
            messagebox.showwarning("Incomplete", "Put assets on both sides first.")
            return
        # Cap check for the user before bothering the AI
        if not self.te._cap_ok_after(self.parent.user_team, user_assets, partner_assets):
            messagebox.showerror("Cap problem",
                                 "This trade puts YOU over the salary cap. Shed salary first.")
            return
        resp = self.te.ai_consider_trade(partner, user_assets, partner_assets,
                                         user_team=self.parent.user_team)
        if resp.decision == 'accept':
            self._complete_trade(partner, user_assets, partner_assets)
            messagebox.showinfo("Trade Accepted", resp.message +
                                "\n\n" + self._last_summary)
        elif resp.decision == 'reject':
            messagebox.showerror("Trade Rejected", resp.message)
        else:
            self._counter_dialog(partner, user_assets, partner_assets, resp)

    def _counter_dialog(self, partner, user_assets, partner_assets, resp):
        dlg = tk.Toplevel(self)
        dlg.title("Counter-offer")
        dlg.geometry("460x260")
        dlg.configure(background=self.parent.BG_COLOR)
        dlg.transient(self)
        ttk.Label(dlg, text=f"{partner.team_name} counters",
                  font=(self.parent.FONT_FAMILY, 14, 'bold'),
                  style='Heading.TLabel').pack(pady=(14, 6))
        ttk.Label(dlg, text=resp.message, style='TLabel',
                  wraplength=400, justify='center',
                  font=(self.parent.FONT_FAMILY, 11)).pack(pady=6)
        btns = ttk.Frame(dlg, style='Panel.TFrame')
        btns.pack(pady=16)
        def accept_counter():
            ua = list(user_assets) + list(resp.want_added)
            pa = list(partner_assets) + list(resp.will_add)
            if not self.te._cap_ok_after(self.parent.user_team, ua, pa):
                messagebox.showerror("Cap problem",
                                     "The counter puts you over the cap.")
                return
            dlg.destroy()
            self._complete_trade(partner, ua, pa)
            messagebox.showinfo("Trade Accepted",
                                "Counter accepted!\n\n" + self._last_summary)
        ttk.Button(btns, text="Accept Counter", command=accept_counter,
                   style='TButton').pack(side='left', padx=8)
        ttk.Button(btns, text="Walk Away", command=dlg.destroy,
                   style='Secondary.TButton').pack(side='left', padx=8)

    def _complete_trade(self, partner, user_assets, partner_assets):
        gm = getattr(self.parent, 'game_manager', None)
        date_str = str(getattr(gm, 'current_date', '')) if gm else ''
        trade = self.te.execute_trade(self.parent.user_team, partner,
                                      user_assets, partner_assets, date_str)
        self._last_summary = trade.summary
        if gm is not None:
            gm.trade_history.append(trade)
            # Media + news
            try:
                traded = [a for a in user_assets if not self.te._is_pick(a)]
                received = [a for a in partner_assets if not self.te._is_pick(a)]
                if hasattr(gm, 'media_system') and gm.media_system:
                    gm.media_system.process_trade(
                        user_team=self.parent.user_team, other_team=partner,
                        traded_players=traded, received_players=received)
            except Exception:
                pass
            try:
                self.parent.add_news_story(f"TRADE: {trade.summary}")
            except Exception:
                pass
        self.trade_offers = {'user': [], 'partner': []}
        self.parent.update_all_views()
        self.update_views()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def _toggle_history(self):
        gm = getattr(self.parent, 'game_manager', None)
        history = list(getattr(gm, 'trade_history', [])) if gm else []
        if self._history_visible:
            self.history_frame.pack_forget()
            self._history_visible = False
            return
        for child in self.history_frame.winfo_children():
            child.destroy()
        ttk.Label(self.history_frame, text=f"Trade History ({len(history)})",
                  font=(self.parent.FONT_FAMILY, 12, 'bold'),
                  style='Heading.TLabel').pack(anchor='w')
        if not history:
            ttk.Label(self.history_frame, text="No trades yet this save.",
                      style='Secondary.TLabel').pack(anchor='w', pady=4)
        else:
            lb = tk.Listbox(self.history_frame, height=5, bg='#232a3a',
                            fg='#e8ecf4', relief='flat')
            lb.pack(fill='x', pady=4)
            for t in reversed(history[-20:]):
                lb.insert(tk.END, f"{t.date} — {t.summary}")
        self.history_frame.pack(fill='x', padx=10, pady=(0, 8), before=self.main_pane)
        self._history_visible = True


class ScoutingWindow(tk.Toplevel):
    """Modern Scouting Department: fog-of-war prospects, regional scouts, draft board."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Scouting Department")
        self.geometry("1280x780")
        self.configure(background=parent.BG_COLOR)
        import scouting as scmod
        self.scmod = scmod
        self._gm = getattr(parent, 'game_manager', parent)
        self.selected_scout = None
        self.selected_prospect = None
        self.filter_var = tk.StringVar(master=self, value="All Prospects")
        self.search_var = tk.StringVar(master=self)
        self.region_var = tk.StringVar(master=self)

        # ---- Header ----
        header = ttk.Frame(self, style='Panel.TFrame', padding=(14, 10))
        header.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(header, text="Scouting Department",
                  font=(parent.FONT_FAMILY, 18, 'bold'),
                  style='Heading.TLabel').pack(side='left')
        n_prospects = len(getattr(parent.league, 'draft_prospects', []) or [])
        ttk.Label(header, text=f"{n_prospects} draft-eligible prospects on the radar",
                  style='Secondary.TLabel').pack(side='left', padx=(12, 0))

        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)

        # ============ LEFT: scouts ============
        left = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(left, weight=1)

        ttk.Label(left, text="YOUR SCOUTS", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.scouts_tree = parent._create_treeview(
            left, {'name': ('Name', 120), 'jpa': ('JPA', 36),
                   'jpp': ('JPP', 36), 'region': ('Region', 90)}, height=6)
        self.scouts_tree.pack(fill='x', pady=(0, 4))
        self.scouts_tree.bind('<<TreeviewSelect>>', self._on_scout_selected)

        reg_frame = ttk.Frame(left, style='Panel.TFrame')
        reg_frame.pack(fill='x', pady=(0, 4))
        ttk.Label(reg_frame, text="Region:", style='Secondary.TLabel').pack(side='left')
        self.region_combo = ttk.Combobox(reg_frame, textvariable=self.region_var,
                                        values=self.scmod.SCOUT_REGIONS,
                                        state='readonly', width=16)
        self.region_combo.pack(side='left', padx=6)
        ttk.Button(reg_frame, text="Assign", command=self._assign_region,
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(reg_frame, text="Clear", command=self._clear_region,
                   style='Secondary.TButton').pack(side='left', padx=2)

        ttk.Button(left, text="Hire Scout", command=self._hire_scout,
                   style='Secondary.TButton').pack(anchor='w', pady=(0, 8))

        ttk.Label(left, text="ACTIVE ASSIGNMENTS", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.assign_tree = parent._create_treeview(
            left, {'player': ('Player', 110), 'view': ('Views', 44),
                   'acc': ('Acc', 36)}, height=8)
        self.assign_tree.pack(fill='both', expand=True)
        ttk.Button(left, text="Remove Assignment", command=self._remove_assignment,
                   style='Secondary.TButton').pack(anchor='w', pady=(6, 0))
        ttk.Label(left, text="Regional scouts file reports automatically every few days.",
                  style='Secondary.TLabel', wraplength=260,
                  font=(parent.FONT_FAMILY, 9)).pack(anchor='w', pady=(6, 0))

        # ============ CENTER: prospects + report ============
        center = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(center, weight=2)

        top_row = ttk.Frame(center, style='Panel.TFrame')
        top_row.pack(fill='x', pady=(0, 4))
        ttk.Label(top_row, text="PROSPECT POOL", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(side='left')
        filt = ttk.Combobox(top_row, textvariable=self.filter_var, width=14,
                            state='readonly',
                            values=["All Prospects", "Forwards", "Defensemen",
                                    "Goalies", "Top 50", "Not Scouted"])
        filt.pack(side='left', padx=(10, 4))
        filt.bind("<<ComboboxSelected>>", lambda e: self._refresh_prospects())
        ttk.Entry(top_row, textvariable=self.search_var, width=14).pack(side='left', padx=4)
        ttk.Button(top_row, text="Search", command=self._refresh_prospects,
                   style='Secondary.TButton').pack(side='left')

        self.prospects_tree = parent._create_treeview(
            center, {'rank': ('#', 36), 'name': ('Name', 140), 'pos': ('Pos', 40),
                     'age': ('Age', 36), 'nat': ('Nat', 70), 'pot': ('Pot', 80),
                     'status': ('Status', 90)}, height=11)
        self.prospects_tree.pack(fill='both', expand=True, pady=(0, 6))
        self.prospects_tree.bind('<<TreeviewSelect>>', self._on_prospect_selected)
        for g in self.scmod.GRADE_ORDER:
            self.prospects_tree.tag_configure(f"pot_{g}",
                                              foreground=self.scmod.grade_color(g))

        # Report card
        self.report_frame = ttk.Frame(center, style='Card.TFrame', padding=10)
        self.report_frame.pack(fill='x')
        self._build_report_card()

        # ============ RIGHT: draft board ============
        right = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(right, weight=1)
        ttk.Label(right, text="MY DRAFT BOARD", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        ttk.Label(right, text="Your rankings drive auto-draft on draft night.",
                  style='Secondary.TLabel', wraplength=240,
                  font=(parent.FONT_FAMILY, 9)).pack(anchor='w', pady=(0, 4))
        self.board_list = tk.Listbox(right, height=24, activestyle='none',
                                     bg='#232a3a', fg='#e8ecf4',
                                     selectbackground='#335577', relief='flat',
                                     highlightthickness=1,
                                     highlightbackground='#3a4a63')
        self.board_list.pack(fill='both', expand=True)
        brow = ttk.Frame(right, style='Panel.TFrame')
        brow.pack(fill='x', pady=(6, 0))
        ttk.Button(brow, text="▲", width=3, command=lambda: self._move_board(-1),
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(brow, text="▼", width=3, command=lambda: self._move_board(1),
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(brow, text="Remove", command=self._remove_board,
                   style='Secondary.TButton').pack(side='left', padx=2)
        ttk.Button(right, text="Reset to Consensus Top 50",
                   command=self._reset_board,
                   style='Secondary.TButton').pack(fill='x', pady=(6, 0))

        self._refresh_all()

    # ------------------------------------------------------------------
    def _build_report_card(self):
        f = self.report_frame
        self.rep_title = ttk.Label(f, text="Select a prospect",
                                  font=(self.parent.FONT_FAMILY, 13, 'bold'),
                                  style='Card.TLabel')
        self.rep_title.pack(anchor='w')
        self.rep_pot = ttk.Label(f, text="", font=(self.parent.FONT_FAMILY, 12, 'bold'),
                                style='Card.TLabel')
        self.rep_pot.pack(anchor='w', pady=(2, 0))
        self.rep_meta = ttk.Label(f, text="", style='Card.TLabel',
                                 font=(self.parent.FONT_FAMILY, 10))
        self.rep_meta.pack(anchor='w')
        cols = ttk.Frame(f, style='Card.TFrame')
        cols.pack(fill='x', pady=(6, 0))
        left_c = ttk.Frame(cols, style='Card.TFrame')
        left_c.pack(side='left', fill='x', expand=True)
        right_c = ttk.Frame(cols, style='Card.TFrame')
        right_c.pack(side='left', fill='x', expand=True)
        ttk.Label(left_c, text="Strengths", style='Card.TLabel',
                  font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_strengths = ttk.Label(left_c, text="—", style='Card.TLabel',
                                      wraplength=260, justify='left')
        self.rep_strengths.pack(anchor='w')
        ttk.Label(right_c, text="Weaknesses", style='Card.TLabel',
                  font=(self.parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w')
        self.rep_weak = ttk.Label(right_c, text="—", style='Card.TLabel',
                                  wraplength=260, justify='left')
        self.rep_weak.pack(anchor='w')
        self.rep_notes = ttk.Label(f, text="", style='Card.TLabel',
                                  wraplength=560, justify='left',
                                  font=(self.parent.FONT_FAMILY, 10))
        self.rep_notes.pack(anchor='w', pady=(6, 0))
        brow = ttk.Frame(f, style='Card.TFrame')
        brow.pack(fill='x', pady=(8, 0))
        ttk.Button(brow, text="Assign Selected Scout",
                   command=self._assign_scout_to_prospect,
                   style='Secondary.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(brow, text="Add to Draft Board",
                   command=self._add_prospect_to_board,
                   style='Secondary.TButton').pack(side='left')

    # ------------------------------------------------------------------
    def _refresh_all(self):
        self._refresh_scouts()
        self._refresh_assignments()
        self._refresh_prospects()
        self._refresh_board()

    def _refresh_scouts(self):
        from game_classes import StaffRole
        tree = self.scouts_tree
        tree.delete(*tree.get_children())
        scouts = [s for s in self.parent.user_team.staff
                  if self.scmod.is_scout(s)]
        tm = self.parent.tree_maps.setdefault(tree, {})
        for s in scouts:
            region = self.scmod.get_scout_region(self._gm, s) or "—"
            item = tree.insert('', 'end', values=(
                getattr(s, 'full_name', '?'),
                getattr(s, 'judging_player_ability', '?'),
                getattr(s, 'judging_player_potential', '?'),
                region))
            tm[item] = s

    def _on_scout_selected(self, event=None):
        sel = self.scouts_tree.selection()
        tm = self.parent.tree_maps.get(self.scouts_tree, {})
        self.selected_scout = tm.get(sel[0]) if sel else None
        if self.selected_scout:
            self.region_var.set(
                self.scmod.get_scout_region(self._gm, self.selected_scout) or "")

    def _assign_region(self):
        if not self.selected_scout:
            messagebox.showwarning("No Scout", "Select a scout first.")
            return
        region = self.region_var.get()
        if not region:
            return
        self.scmod.set_scout_region(self._gm, self.selected_scout, region)
        self._refresh_scouts()

    def _clear_region(self):
        if self.selected_scout:
            self.scmod.set_scout_region(self._gm, self.selected_scout, None)
            self.region_var.set("")
            self._refresh_scouts()

    def _hire_scout(self):
        from game_classes import Staff, StaffRole
        import random as _r
        names = [("Jim", "Gregory"), ("Marie", "Labelle"), ("Ken", "Holland"),
                 ("Sofia", "Lindqvist"), ("Petr", "Novak"), ("Dave", "Morrison")]
        fn, ln = _r.choice(names)
        scout = Staff(first_name=fn, last_name=ln, role=StaffRole.AMATEUR_SCOUT)
        self.parent.user_team.staff.append(scout)
        messagebox.showinfo("Scout Hired",
                            f"{scout.full_name} joined your scouting department.\n"
                            f"Assign them a region to start filing reports.")
        self._refresh_scouts()

    def _refresh_assignments(self):
        tree = self.assign_tree
        tree.delete(*tree.get_children())
        tm = self.parent.tree_maps.setdefault(tree, {})
        for player, scout in getattr(self.parent, 'scouting_assignments', {}).items():
            report = self.parent.user_team.scouting_reports.get(player.id)
            views = getattr(report, 'viewings', 0) if report else 0
            acc = getattr(report, 'accuracy', '—') if report else '—'
            item = tree.insert('', 'end', values=(
                player.full_name,
                views, acc))
            tm[item] = player

    def _remove_assignment(self):
        sel = self.assign_tree.selection()
        tm = self.parent.tree_maps.get(self.assign_tree, {})
        player = tm.get(sel[0]) if sel else None
        if player and player in getattr(self.parent, 'scouting_assignments', {}):
            del self.parent.scouting_assignments[player]
            self._refresh_assignments()
            self._refresh_prospects()

    # ------------------------------------------------------------------
    def _filtered_prospects(self):
        all_p = sorted(getattr(self.parent.league, 'draft_prospects', []) or [],
                       key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)
        ft = self.filter_var.get()
        from game_classes import PlayerPosition
        if ft == "Forwards":
            all_p = [p for p in all_p if p.primary_position in
                     (PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                      PlayerPosition.RIGHT_WING)]
        elif ft == "Defensemen":
            all_p = [p for p in all_p if p.primary_position in
                     (PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                      PlayerPosition.DEFENSE)]
        elif ft == "Goalies":
            all_p = [p for p in all_p
                     if p.primary_position == PlayerPosition.GOALIE]
        elif ft == "Top 50":
            all_p = all_p[:50]
        elif ft == "Not Scouted":
            reports = self.parent.user_team.scouting_reports
            all_p = [p for p in all_p if p.id not in reports]
        q = self.search_var.get().lower().strip()
        if q:
            all_p = [p for p in all_p if q in p.full_name.lower()]
        return all_p

    def _refresh_prospects(self):
        tree = self.prospects_tree
        tree.delete(*tree.get_children())
        tm = self.parent.tree_maps.setdefault(tree, {})
        reports = self.parent.user_team.scouting_reports
        assigns = getattr(self.parent, 'scouting_assignments', {})
        for i, p in enumerate(self._filtered_prospects()[:400]):
            report = reports.get(p.id)
            if report:
                pot = self.scmod.report_potential_display(report, p)
                status = f"Scouted ({getattr(report, 'accuracy', '?')})"
                top_grade = pot.split("–")[-1].strip()
            elif p in assigns:
                pot = self.scmod.consensus_range(p)
                status = "In progress"
                top_grade = pot.split("–")[-1].strip()
            else:
                pot = self.scmod.consensus_range(p)
                status = "—"
                top_grade = pot.split("–")[-1].strip()
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            tag = f"pot_{top_grade}" if top_grade in self.scmod.GRADE_ORDER else ""
            item = tree.insert('', 'end', values=(
                i + 1, p.full_name, pos, p.age,
                getattr(p, 'nationality', '?'), pot, status),
                tags=(tag,) if tag else ())
            tm[item] = p

    def _on_prospect_selected(self, event=None):
        sel = self.prospects_tree.selection()
        tm = self.parent.tree_maps.get(self.prospects_tree, {})
        self.selected_prospect = tm.get(sel[0]) if sel else None
        self._show_report()

    def _show_report(self):
        p = self.selected_prospect
        if p is None:
            return
        reports = self.parent.user_team.scouting_reports
        report = reports.get(p.id)
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        self.rep_title.config(
            text=f"{p.full_name}  ·  {pos}  ·  {p.age}  ·  {getattr(p, 'nationality', '?')}")
        if report:
            pot = self.scmod.report_potential_display(report, p)
            top = pot.split("–")[-1].strip()
            self.rep_pot.config(text=f"Potential: {pot}",
                                foreground=self.scmod.grade_color(top))
            info = self.scmod.report_summary(report)
            self.rep_meta.config(
                text=f"Report accuracy {info['accuracy']}  ·  {info['viewings']} viewings  ·  "
                     f"Scout: {info['scout']}  ·  Region: {info['region']}")
            self.rep_strengths.config(
                text="\n".join(f"• {s}" for s in info['strengths']) or "—")
            self.rep_weak.config(
                text="\n".join(f"• {w}" for w in info['weaknesses']) or "—")
            notes = []
            if info['comparable'] != '—':
                notes.append(f"Comparable: {info['comparable']}")
            if info['projection'] != '—':
                notes.append(f"ETA: {info['projection']}")
            if info['notes']:
                notes.append(info['notes'][:220])
            self.rep_notes.config(text="   ".join(notes))
        else:
            pot = self.scmod.consensus_range(p)
            top = pot.split("–")[-1].strip()
            self.rep_pot.config(text=f"Potential: {pot}  (consensus — scout for certainty)",
                                foreground=self.scmod.grade_color(top))
            assigned = p in getattr(self.parent, 'scouting_assignments', {})
            self.rep_meta.config(
                text="No report yet — " +
                     ("a scout is watching." if assigned else "assign a scout or a region."))
            self.rep_strengths.config(text="—")
            self.rep_weak.config(text="—")
            self.rep_notes.config(text="")

    def _assign_scout_to_prospect(self):
        p = self.selected_prospect
        if p is None:
            messagebox.showwarning("No Prospect", "Select a prospect first.")
            return
        scout = self.selected_scout
        if scout is None:
            from game_classes import StaffRole
            scouts = [s for s in self.parent.user_team.staff
                      if self.scmod.is_scout(s)]
            if not scouts:
                messagebox.showwarning("No Scouts", "Hire a scout first.")
                return
            scout = scouts[0]
        assigns = self.parent.scouting_assignments
        if p in assigns:
            messagebox.showinfo("Already Assigned", "This prospect is already being scouted.")
            return
        if len(assigns) >= 30:
            messagebox.showwarning("Limit", "You have 30 active assignments already.")
            return
        assigns[p] = scout
        messagebox.showinfo("Assignment Started",
                            f"{scout.full_name} will scout {p.full_name}.")
        self._refresh_assignments()
        self._refresh_prospects()
        self._show_report()

    # ------------------------------------------------------------------
    def _refresh_board(self):
        lb = self.board_list
        lb.delete(0, tk.END)
        ids = self.scmod.get_draft_board(self.parent.user_team)
        by_id = {p.id: p for p in
                 getattr(self.parent.league, 'draft_prospects', []) or []}
        # prune missing
        ids = [i for i in ids if i in by_id]
        self.scmod.set_draft_board(self.parent.user_team, ids)
        for n, pid in enumerate(ids, 1):
            p = by_id[pid]
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            lb.insert(tk.END, f"{n}. {p.full_name} ({pos})")

    def _add_prospect_to_board(self):
        p = self.selected_prospect
        if p is None:
            return
        ids = self.scmod.get_draft_board(self.parent.user_team)
        if p.id not in ids:
            ids.append(p.id)
            self.scmod.set_draft_board(self.parent.user_team, ids)
            self._refresh_board()

    def _move_board(self, direction):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + direction
        ids = self.scmod.get_draft_board(self.parent.user_team)
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self.scmod.set_draft_board(self.parent.user_team, ids)
            self._refresh_board()
            lb.select_set(j)

    def _remove_board(self):
        lb = self.board_list
        sel = lb.curselection()
        if not sel:
            return
        ids = self.scmod.get_draft_board(self.parent.user_team)
        del ids[sel[0]]
        self.scmod.set_draft_board(self.parent.user_team, ids)
        self._refresh_board()

    def _reset_board(self):
        prospects = sorted(getattr(self.parent.league, 'draft_prospects', []) or [],
                           key=lambda p: getattr(p, 'draft_ranking', 0),
                           reverse=True)[:50]
        self.scmod.set_draft_board(self.parent.user_team, [p.id for p in prospects])
        self._refresh_board()


class DraftWindow(tk.Toplevel):
    """Draft night war room: live board, ticker, shortlist, draft-day trades, grades."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("NHL Entry Draft")
        self.geometry("1280x800")
        self.configure(background=parent.BG_COLOR)
        import draft_night as dn
        import scouting as scmod
        import trade_engine as te
        self.dn = dn
        self.scmod = scmod
        self.te = te

        self.current_round = 1
        self.total_rounds = 7
        self.current_pick = 0
        self.draft_order = []          # [round, team, draft_pick]
        self.picks_made = []           # (team_name, overall, player)
        self.selected_prospect = None
        self.strategy_var = tk.StringVar(master=self, value="BPA")
        self.pos_filter_var = tk.StringVar(master=self, value="All Positions")
        self._ai_after_id = None

        # ---- Header ----
        header = ttk.Frame(self, style='Panel.TFrame', padding=(14, 10))
        header.pack(fill='x', padx=10, pady=(10, 0))
        title_box = ttk.Frame(header, style='Panel.TFrame')
        title_box.pack(side='left')
        ttk.Label(title_box, text="NHL Entry Draft",
                  font=(parent.FONT_FAMILY, 18, 'bold'),
                  style='Heading.TLabel').pack(anchor='w')
        self.draft_status_label = ttk.Label(title_box, text="Draft Night",
                                            style='Secondary.TLabel')
        self.draft_status_label.pack(anchor='w')
        # On-the-clock spotlight
        self.clock_frame = ttk.Frame(header, style='Card.TFrame', padding=(16, 6))
        self.clock_frame.pack(side='right', padx=10)
        ttk.Label(self.clock_frame, text="ON THE CLOCK",
                  style='Card.TLabel', font=(parent.FONT_FAMILY, 9, 'bold')).pack()
        self.clock_label = ttk.Label(self.clock_frame, text="—",
                                     style='Card.TLabel',
                                     font=(parent.FONT_FAMILY, 15, 'bold'))
        self.clock_label.pack()
        self.pick_info_label = ttk.Label(self.clock_frame, text="",
                                         style='Card.TLabel')
        self.pick_info_label.pack()

        # ---- 3 columns ----
        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=10, pady=8)

        # LEFT: draft board
        left = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(left, weight=2)
        ttk.Label(left, text="DRAFT BOARD", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.draft_results_tree = parent._create_treeview(
            left, {'pick': ('#', 40), 'team': ('Team', 130),
                   'player': ('Player', 150), 'pos': ('Pos', 40),
                   'pot': ('Pot', 60)}, height=30)
        self.draft_results_tree.pack(fill='both', expand=True)

        # CENTER: war room
        center = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(center, weight=1)

        ttk.Label(center, text="WAR ROOM", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.next_pick_label = ttk.Label(center, text="", style='TLabel',
                                         font=(parent.FONT_FAMILY, 11, 'bold'))
        self.next_pick_label.pack(anchor='w', pady=(0, 4))

        strat_row = ttk.Frame(center, style='Panel.TFrame')
        strat_row.pack(fill='x', pady=(0, 4))
        ttk.Label(strat_row, text="Strategy:", style='Secondary.TLabel').pack(side='left')
        ttk.Radiobutton(strat_row, text="Best Available", variable=self.strategy_var,
                        value="BPA").pack(side='left', padx=4)
        ttk.Radiobutton(strat_row, text="Positional Need", variable=self.strategy_var,
                        value="Need").pack(side='left', padx=4)

        filt_row = ttk.Frame(center, style='Panel.TFrame')
        filt_row.pack(fill='x', pady=(0, 4))
        ttk.Label(filt_row, text="Show:", style='Secondary.TLabel').pack(side='left')
        pos_combo = ttk.Combobox(filt_row, textvariable=self.pos_filter_var,
                                 values=["All Positions", "Forwards", "Defensemen", "Goalies"],
                                 state='readonly', width=14)
        pos_combo.pack(side='left', padx=4)
        pos_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_shortlist())

        ttk.Label(center, text="SHORTLIST", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(4, 2))
        self.shortlist = tk.Listbox(center, height=14, activestyle='none',
                                    bg='#232a3a', fg='#e8ecf4',
                                    selectbackground='#335577', relief='flat',
                                    highlightthickness=1,
                                    highlightbackground='#3a4a63')
        self.shortlist.pack(fill='x', pady=(0, 4))
        self.shortlist.bind('<<ListboxSelect>>', self._on_shortlist_select)

        self.selected_label = ttk.Label(center, text="No prospect selected",
                                        style='Secondary.TLabel', wraplength=300)
        self.selected_label.pack(anchor='w', pady=(0, 6))

        btn_col = ttk.Frame(center, style='Panel.TFrame')
        btn_col.pack(fill='x')
        self.draft_button = ttk.Button(btn_col, text="Draft Selected",
                                       command=self.make_user_pick, style='TButton')
        self.draft_button.pack(fill='x', pady=2)
        self.auto_button = ttk.Button(btn_col, text="Auto Pick (My Board)",
                                      command=self.auto_pick,
                                      style='Secondary.TButton')
        self.auto_button.pack(fill='x', pady=2)
        self.trade_pick_button = ttk.Button(btn_col, text="Trade This Pick",
                                            command=self.trade_current_pick,
                                            style='Secondary.TButton')
        self.trade_pick_button.pack(fill='x', pady=2)

        # RIGHT: ticker
        right = ttk.Frame(main_pane, style='Panel.TFrame', padding=8)
        main_pane.add(right, weight=1)
        ttk.Label(right, text="DRAFT TICKER", style='Secondary.TLabel',
                  font=(parent.FONT_FAMILY, 10, 'bold')).pack(anchor='w', pady=(0, 4))
        self.ticker = tk.Listbox(right, activestyle='none', bg='#141a26',
                                 fg='#c8d2e3', relief='flat', height=30,
                                 highlightthickness=1,
                                 highlightbackground='#3a4a63')
        self.ticker.pack(fill='both', expand=True)
        self.grades_button = ttk.Button(right, text="Draft Grades",
                                        command=self.show_grades,
                                        style='Secondary.TButton',
                                        state='disabled')
        self.grades_button.pack(fill='x', pady=(6, 0))

        self.start_draft()

    # ------------------------------------------------------------------
    def start_draft(self):
        # Make sure every team owns its picks (idempotent if already done)
        try:
            self.parent.league.initialize_all_draft_picks()
        except Exception:
            pass
        current_year = self.parent.league.season_year
        self.draft_order = []
        try:
            order = self.parent.league.get_draft_order(current_year)
        except Exception:
            order = []
        for overall_pick, team, draft_pick in order:
            try:
                draft_pick.overall_pick = overall_pick
            except Exception:
                pass
            self.draft_order.append([draft_pick.round, team, draft_pick])
        if not self.draft_order:
            sorted_teams = sorted(self.parent.league.teams,
                                  key=lambda t: self.parent.league.standings[t.team_name]['Points'])
            for round_num in range(1, self.total_rounds + 1):
                for team in sorted_teams:
                    self.draft_order.append([round_num, team, None])
        self.current_pick = 0
        self.picks_made = []
        self.draft_results_tree.delete(*self.draft_results_tree.get_children())
        self.ticker.delete(0, tk.END)
        self._ticker("Welcome to draft night. The floor is buzzing.")
        self._refresh_shortlist()
        self.process_draft_pick()

    # ------------------------------------------------------------------
    def _ticker(self, line):
        self.ticker.insert(0, line)
        if self.ticker.size() > 120:
            self.ticker.delete(120, tk.END)

    def _available_prospects(self):
        return sorted(self.parent.league.draft_prospects,
                      key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)

    def _board_sorted_available(self):
        """Available prospects ordered by the user's draft board, then consensus."""
        avail = self._available_prospects()
        rank = self.scmod.board_rank_map(self.parent.user_team)
        if not rank:
            return avail
        return sorted(avail, key=lambda p: rank.get(p.id, 10_000 + getattr(p, 'draft_ranking', 0) * -1))

    def _refresh_shortlist(self):
        self.shortlist.delete(0, tk.END)
        self._shortlist_players = []
        filt = self.pos_filter_var.get()
        from game_classes import PlayerPosition
        reports = self.parent.user_team.scouting_reports
        count = 0
        for p in self._board_sorted_available():
            if filt == "Forwards" and p.primary_position not in (
                    PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                    PlayerPosition.RIGHT_WING):
                continue
            if filt == "Defensemen" and p.primary_position not in (
                    PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
                    PlayerPosition.DEFENSE):
                continue
            if filt == "Goalies" and p.primary_position != PlayerPosition.GOALIE:
                continue
            report = reports.get(p.id)
            pot = (self.scmod.report_potential_display(report, p) if report
                   else self.scmod.consensus_range(p))
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            self.shortlist.insert(tk.END, f"{p.full_name}  ({pos})  {pot}")
            self._shortlist_players.append(p)
            count += 1
            if count >= 30:
                break

    def _on_shortlist_select(self, event=None):
        sel = self.shortlist.curselection()
        if not sel:
            return
        p = self._shortlist_players[sel[0]]
        self.selected_prospect = p
        reports = self.parent.user_team.scouting_reports
        report = reports.get(p.id)
        pot = (self.scmod.report_potential_display(report, p) if report
               else self.scmod.consensus_range(p) + " (consensus)")
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        self.selected_label.config(
            text=f"Selected: {p.full_name} ({pos}, {p.age}) — Potential {pot}")

    # ------------------------------------------------------------------
    def process_draft_pick(self):
        if self.current_pick >= len(self.draft_order):
            self.end_draft()
            return
        round_num, team_on_clock, _dp = self.draft_order[self.current_pick]
        if round_num != self.current_round:
            self.current_round = round_num
        overall = self.current_pick + 1
        pick_in_round = (self.current_pick %
                         max(1, len(self.parent.league.teams))) + 1

        self.draft_status_label.config(
            text=f"Round {round_num} of {self.total_rounds}")
        self.clock_label.config(text=team_on_clock.team_name)
        self.pick_info_label.config(
            text=f"Pick #{overall}  (Round {round_num}, #{pick_in_round} in round)")

        is_user = team_on_clock == self.parent.user_team
        state = 'normal' if is_user else 'disabled'
        self.draft_button.config(state=state)
        self.auto_button.config(state=state)
        self.trade_pick_button.config(state=state)

        # Your next pick info
        nxt = next((i for i in range(self.current_pick, len(self.draft_order))
                    if self.draft_order[i][1] == self.parent.user_team), None)
        if nxt is not None:
            r = self.draft_order[nxt][0]
            self.next_pick_label.config(
                text=f"Your next pick: #{nxt + 1} (Round {r})")
        else:
            self.next_pick_label.config(text="No picks remaining")

        if not is_user:
            if self._ai_after_id:
                try:
                    self.after_cancel(self._ai_after_id)
                except Exception:
                    pass
            self._ai_after_id = self.after(650, self.ai_make_pick)

    def ai_make_pick(self):
        self._ai_after_id = None
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        available = self._available_prospects()
        if not available:
            self.end_draft()
            return
        needs = self.te.team_needs(team_on_clock)
        # Consider top 12, weigh positional need + randomness
        candidates = available[:12]
        round_num = self.draft_order[self.current_pick][0]
        scored = []
        for p in candidates:
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            base = getattr(p, 'draft_ranking', 0)
            if pos in needs[:2]:
                base *= 1.08
            if pos == 'G' and round_num <= 1:
                base *= 0.80  # goalies rarely go top-10
            base *= random.uniform(0.94, 1.06)
            scored.append((base, p))
        scored.sort(key=lambda s: s[0], reverse=True)
        selected = scored[0][1]
        # Reach / steal detection for the ticker
        idx = available.index(selected)
        self.execute_pick(team_on_clock, selected,
                          reach=idx >= 8, steal=idx == 0 and self.current_pick >= 4)

    def make_user_pick(self):
        if not self.selected_prospect:
            messagebox.showwarning("No Prospect", "Select a prospect from the shortlist.")
            return
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            return
        p = self.selected_prospect
        if p not in self.parent.league.draft_prospects:
            messagebox.showwarning("Unavailable", "That prospect was already drafted.")
            self._refresh_shortlist()
            return
        if not messagebox.askyesno("Confirm Pick",
                                   f"Draft {p.full_name}?\nThis cannot be undone."):
            return
        self.execute_pick(team_on_clock, p)

    def auto_pick(self):
        _r, team_on_clock, _dp = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            return
        available = self._board_sorted_available()
        if not available:
            return
        if self.strategy_var.get() == "Need":
            needs = self.te.team_needs(self.parent.user_team)
            pick = None
            for p in available[:8]:
                try:
                    pos = p.primary_position.value
                except Exception:
                    pos = "?"
                if pos in needs[:3]:
                    pick = p
                    break
            selected = pick or available[0]
        else:
            selected = available[0]
        self.execute_pick(team_on_clock, selected)

    def execute_pick(self, team, player, reach=False, steal=False):
        round_num, _t, _dp = self.draft_order[self.current_pick]
        overall = self.current_pick + 1
        team.add_player(player, "prospects")
        try:
            self.parent.league.draft_prospects.remove(player)
        except ValueError:
            pass
        try:
            pos = player.primary_position.value
        except Exception:
            pos = "?"
        self.draft_results_tree.insert('', 0, values=(
            overall, team.team_name, player.full_name, pos,
            getattr(player, 'potential_grade', '?')))
        self._ticker(self.dn.ticker_line(overall, team.team_name, player,
                                         round_num, reach=reach, steal=steal))
        self.picks_made.append((team.team_name, overall, player))
        try:
            self.parent.news_log.append({
                'date': self.parent.current_date, 'type': 'draft',
                'story': f"With pick #{overall}, the {team.team_name} select "
                         f"{player.full_name} ({pos})."})
        except Exception:
            pass
        self.current_pick += 1
        self.selected_prospect = None
        self.selected_label.config(text="No prospect selected")
        self._refresh_shortlist()
        # Keep the board scrolled to the newest pick
        kids = self.draft_results_tree.get_children()
        if kids:
            self.draft_results_tree.see(kids[0])
        self.process_draft_pick()

    # ------------------------------------------------------------------
    def trade_current_pick(self):
        """Draft-day trade: swap your current pick with a partner's pick."""
        if self.current_pick >= len(self.draft_order):
            return
        _r, team_on_clock, user_pick = self.draft_order[self.current_pick]
        if team_on_clock != self.parent.user_team:
            messagebox.showinfo("Not Your Pick", "You can only trade your own pick.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Trade this pick")
        dlg.geometry("480x420")
        dlg.configure(background=self.parent.BG_COLOR)
        dlg.transient(self)
        overall = self.current_pick + 1
        ttk.Label(dlg, text=f"Your pick: #{overall} (Round {_r})",
                  font=(self.parent.FONT_FAMILY, 12, 'bold'),
                  style='TLabel').pack(pady=(12, 4))
        ttk.Label(dlg, text="Select a partner and one of their upcoming picks:",
                  style='Secondary.TLabel').pack(pady=(0, 8))

        teams = sorted(t.team_name for t in self.parent.league.teams
                       if t != self.parent.user_team)
        pvar = tk.StringVar(master=dlg)
        combo = ttk.Combobox(dlg, textvariable=pvar, values=teams,
                             state='readonly', width=30)
        combo.pack(pady=4)

        lb = tk.Listbox(dlg, height=10, bg='#232a3a', fg='#e8ecf4',
                        selectbackground='#335577', relief='flat')
        lb.pack(fill='both', expand=True, padx=14, pady=6)

        def _partner_picks(name):
            team = next((t for t in self.parent.league.teams
                         if t.team_name == name), None)
            out = []
            for i in range(self.current_pick + 1, len(self.draft_order)):
                r, t, dp = self.draft_order[i]
                if t == team and dp is not None:
                    out.append((i, dp, r))
            return team, out

        def _refresh_lb(event=None):
            lb.delete(0, tk.END)
            _t, picks = _partner_picks(pvar.get())
            for i, dp, r in picks:
                val = self.te.pick_trade_value(dp)
                lb.insert(tk.END, f"#{i + 1} (Round {r}) — value {val}")
            _store(event)

        def _store(event=None):
            dlg._picks = _partner_picks(pvar.get())[1]

        dlg._picks = []
        combo.bind("<<ComboboxSelected>>", _refresh_lb)

        info = ttk.Label(dlg, text="", style='TLabel', wraplength=440,
                         justify='center')
        info.pack(pady=4)

        def _update_info(event=None):
            sel = lb.curselection()
            if not sel or not dlg._picks:
                info.config(text="")
                return
            i, dp, r = dlg._picks[sel[0]]
            uv = self.dn.pick_slot_value(overall)
            tv = self.dn.pick_slot_value(i + 1)
            if uv > tv:
                info.config(text=f"You give #{overall} (slot value {uv}), "
                                 f"get #{i + 1} (slot value {tv}). They may want more.")
            elif tv > uv:
                info.config(text=f"You give #{overall} (slot value {uv}), "
                                 f"get #{i + 1} (slot value {tv}). Good value for you.")
            else:
                info.config(text="Even swap on paper.")

        lb.bind('<<ListboxSelect>>', _update_info)

        def _propose():
            sel = lb.curselection()
            if not sel or not dlg._picks:
                return
            j, partner_pick, _r2 = dlg._picks[sel[0]]
            partner = next(t for t in self.parent.league.teams
                           if t.team_name == pvar.get())
            resp = self.te.ai_consider_trade(
                partner, [user_pick], [partner_pick],
                user_team=self.parent.user_team)
            if resp.decision == 'reject':
                messagebox.showerror("Rejected", resp.message)
                return
            if resp.decision == 'counter':
                extra = resp.want_added + resp.will_add
                detail = "; ".join(self.te.asset_label(a) for a in extra)
                if not messagebox.askyesno("Counter-offer",
                                           f"{resp.message}\n\nAccept?"):
                    return
                self._execute_pick_swap(j, user_pick, partner_pick,
                                        resp.want_added, resp.will_add)
            else:
                self._execute_pick_swap(j, user_pick, partner_pick, [], [])
            dlg.destroy()
            messagebox.showinfo("Trade Complete", "Pick swap completed.")
            self.process_draft_pick()

        ttk.Button(dlg, text="Propose Swap", command=_propose,
                   style='TButton').pack(pady=10)

    def _swap_pick_owner(self, draft_pick, new_team):
        """Point a draft pick (and its draft-order slot) at a new owner."""
        try:
            draft_pick.current_team = new_team.team_name
        except Exception:
            pass
        for entry in self.draft_order:
            if entry[2] is draft_pick:
                entry[1] = new_team

    def _execute_pick_swap(self, partner_idx, user_pick, partner_pick,
                           want_added, will_add):
        user_team = self.parent.user_team
        partner_team = self.draft_order[partner_idx][1]
        # Swap the picks
        self._swap_pick_owner(user_pick, partner_team)
        self._swap_pick_owner(partner_pick, user_team)
        # Move any extra assets
        for a in want_added:  # user gives more
            if self.te._is_pick(a):
                self._swap_pick_owner(a, partner_team)
            else:
                try:
                    user_team.remove_player(a)
                    partner_team.add_player(a)
                except Exception:
                    pass
        for a in will_add:  # partner sweetens
            if self.te._is_pick(a):
                self._swap_pick_owner(a, user_team)
            else:
                try:
                    partner_team.remove_player(a)
                    user_team.add_player(a)
                except Exception:
                    pass
        # History + news
        gm = getattr(self.parent, 'game_manager', None)
        summary = (f"{user_team.team_name} acquires pick "
                   f"#{partner_idx + 1} from {partner_team.team_name}.")
        if gm is not None:
            if not hasattr(gm, 'trade_history'):
                gm.trade_history = []
            gm.trade_history.append(self.te.CompletedTrade(
                str(getattr(gm, 'current_date', '')), user_team.team_name,
                partner_team.team_name,
                [self.te.asset_label(user_pick)],
                [self.te.asset_label(partner_pick)], summary))
        try:
            self.parent.add_news_story(f"DRAFT TRADE: {summary}")
        except Exception:
            pass
        self._ticker(f"TRADE: {summary}")

    # ------------------------------------------------------------------
    def show_grades(self):
        grades = self.dn.draft_grades(self.picks_made)
        dlg = tk.Toplevel(self)
        dlg.title("Draft Grades")
        dlg.geometry("420x520")
        dlg.configure(background=self.parent.BG_COLOR)
        dlg.transient(self)
        ttk.Label(dlg, text="Draft Grades",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='Heading.TLabel').pack(pady=12)
        lb = tk.Listbox(dlg, bg='#232a3a', fg='#e8ecf4', relief='flat',
                        font=(self.parent.FONT_FAMILY, 11))
        lb.pack(fill='both', expand=True, padx=14, pady=6)
        user_grade = None
        for team, grade, ratio in grades:
            lb.insert(tk.END, f"  {grade}   {team}")
            lb.itemconfig(tk.END, foreground=self.dn.grade_color(grade))
            if team == self.parent.user_team.team_name:
                user_grade = grade
        if user_grade:
            ttk.Label(dlg, text=f"Your draft grade: {user_grade}",
                      font=(self.parent.FONT_FAMILY, 13, 'bold'),
                      style='TLabel',
                      foreground=self.dn.grade_color(user_grade)).pack(pady=10)

    def end_draft(self):
        if self._ai_after_id:
            try:
                self.after_cancel(self._ai_after_id)
            except Exception:
                pass
        self._ai_after_id = None
        self.draft_status_label.config(text="Draft Complete")
        self.clock_label.config(text="—")
        self.pick_info_label.config(text="All 7 rounds complete")
        self.draft_button.config(state='disabled')
        self.auto_button.config(state='disabled')
        self.trade_pick_button.config(state='disabled')
        self.grades_button.config(state='normal')
        self._ticker("That's a wrap on draft night.")
        self.show_grades()


class ScheduleWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("League Schedule")
        self.geometry("900x700")
        self.configure(background='#1E1E1E')

        # Main container
        main_container = ttk.Frame(self)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        schedule_notebook = ttk.Notebook(main_container)
        schedule_notebook.pack(fill='both', expand=True, pady=(0, 10))
        
        columns = {'date': ('Date', 100), 'away': ('Away Team', 200), 'score': ('Score', 100), 'home': ('Home Team', 200), 'status': ('Status', 100)}
        
        my_team_frame = ttk.Frame(schedule_notebook)
        self.my_schedule_tree = parent._create_treeview(my_team_frame, columns, 25)
        self.my_schedule_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Bind double-click event for my team games
        self.my_schedule_tree.bind('<Double-1>', self.on_game_double_click)
        self.my_schedule_tree.bind('<Button-3>', self.show_game_context_menu)
        
        schedule_notebook.add(my_team_frame, text='My Team Schedule')
        
        league_frame = ttk.Frame(schedule_notebook)
        self.league_schedule_tree = parent._create_treeview(league_frame, columns, 25)
        self.league_schedule_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Bind double-click event for league games
        self.league_schedule_tree.bind('<Double-1>', self.on_game_double_click)
        self.league_schedule_tree.bind('<Button-3>', self.show_game_context_menu)
        
        schedule_notebook.add(league_frame, text='League Schedule')
        
        # Action buttons
        self.create_action_buttons(main_container)
        
        # Store schedule data for game launching
        self.schedule_data = {}
        
        self.update_views()

    def create_action_buttons(self, parent):
        """Create action buttons for schedule operations."""
        button_frame = ttk.Frame(parent, style='Panel.TFrame')
        button_frame.pack(fill='x', pady=(10, 0))
        
        # Watch Game button
        self.watch_game_btn = ttk.Button(
            button_frame,
            text="🎥 Watch Game",
            command=self.watch_selected_game,
            style='Accent.TButton'
        )
        self.watch_game_btn.pack(side='left', padx=(0, 10))
        
        # Simulate Game button
        self.simulate_game_btn = ttk.Button(
            button_frame,
            text="Simulate Game", 
            command=self.simulate_selected_game,
            style='TButton'
        )
        self.simulate_game_btn.pack(side='left', padx=(0, 10))
        
        # Refresh button
        ttk.Button(
            button_frame,
            text="🔄 Refresh",
            command=self.update_views,
            style='TButton'
        ).pack(side='right')
        
    def on_game_double_click(self, event):
        """Handle double-click on a game - launch game viewer."""
        self.watch_selected_game()
        
    def show_game_context_menu(self, event):
        """Show context menu for game operations."""
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return
            
        menu = tk.Menu(self, tearoff=0, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        menu.add_command(label="🎥 Watch Game", command=self.watch_selected_game)
        menu.add_command(label="⚡ Simulate Game", command=self.simulate_selected_game)
        menu.add_separator()
        menu.add_command(label="📊 Game Stats", command=self.view_game_stats)
        menu.add_command(label="📰 Game Recap", command=self.view_game_recap)
        
        menu.tk_popup(event.x_root, event.y_root)
        
    def get_selected_game_data(self):
        """Get data for the currently selected game."""
        # Try to get selection from current tab
        current_tab = None
        try:
            notebook_widget = self.children['!frame']['!notebook']
            current_tab_index = notebook_widget.index(notebook_widget.select())
            if current_tab_index == 0:  # My Team Schedule
                tree = self.my_schedule_tree
            else:  # League Schedule
                tree = self.league_schedule_tree
        except:
            # Fallback to my team schedule
            tree = self.my_schedule_tree
            
        selection = tree.selection()
        if not selection:
            return None
            
        item = selection[0]
        values = tree.item(item, 'values')
        if not values or len(values) < 4:
            return None
            
        # Parse the selected game data
        date_str, away_team_name, score, home_team_name = values[:4]
        
        # Find the actual game in the schedule
        for game_date, home_team, away_team in self.parent.league.schedule:
            if (home_team.team_name == home_team_name and 
                away_team.team_name == away_team_name and
                game_date.strftime("%b %d, %Y") == date_str):
                
                return {
                    'date': game_date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'score': score,
                    'has_been_played': score != "- : -"
                }
        return None
        
    def watch_selected_game(self):
        """Launch the game viewer for the selected game."""
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected", "Please select a game to watch.")
            return
            
        if not game_data['has_been_played']:
            # Game hasn't been played yet - simulate it first
            response = tk.messagebox.askyesno("Game Not Played", 
                                           f"This game hasn't been played yet.\n\n"
                                           f"Would you like to simulate and watch it?")
            if not response:
                return
                
        self._launch_game_viewer(game_data)
        
    def simulate_selected_game(self):
        """Simulate the selected game without watching."""
        game_data = self.get_selected_game_data()
        if not game_data:
            tk.messagebox.showwarning("No Game Selected", "Please select a game to simulate.")
            return
            
        if game_data['has_been_played']:
            tk.messagebox.showinfo("Game Already Played", "This game has already been played.")
            return
            
        # Simulate the game
        self._simulate_game(game_data)
        self.update_views()
        
    def _launch_game_viewer(self, game_data):
        """Launch the enhanced game viewer for a specific game."""
        try:
            from GAME_VIEWER import launch_game_viewer
            from simulation import GameSim
            
            home_team = game_data['home_team']
            away_team = game_data['away_team']
            
            # Create or retrieve game simulation
            if not game_data['has_been_played']:
                # Simulate the game for viewing
                sim = GameSim(home_team, away_team)
                sim.run()
                
                # Store the result
                game_result = {
                    'date': game_data['date'],
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': sim.home_score,
                    'away_score': sim.away_score
                }
                
                # Add to game results if not already there
                if not any(r['date'] == game_data['date'] and 
                          r['home_team'] == home_team and 
                          r['away_team'] == away_team 
                          for r in self.parent.game_results):
                    self.parent.game_results.append(game_result)
                    
                # Update team stats
                self._update_team_stats_from_game(game_result)
                
            else:
                # Find existing game result and create simulation from it
                sim = None
                for result in self.parent.game_results:
                    if (result['date'] == game_data['date'] and
                        result['home_team'] == home_team and
                        result['away_team'] == away_team):
                        # Create a simulation with the known result
                        sim = GameSim(home_team, away_team)
                        sim.home_score = result['home_score']
                        sim.away_score = result['away_score']
                        # Generate some sample events for viewing
                        sim.run()
                        break
                
                if not sim:
                    # Create new simulation as fallback
                    sim = GameSim(home_team, away_team)
                    sim.run()
            
            # Launch the game viewer with simulation data
            event_log = getattr(sim, 'event_log', [])
            duration = 3600  # 60 minutes total game time
            
            launch_game_viewer(
                events=event_log,
                duration=duration,
                home_team_name=home_team.team_name,
                away_team_name=away_team.team_name
            )
            
        except Exception as e:
            tk.messagebox.showerror("Game Viewer Error", 
                                   f"Failed to launch game viewer:\n{str(e)}")
            print(f"Game viewer launch error: {e}")
            
    def _simulate_game(self, game_data):
        """Simulate a game and store the results."""
        try:
            from simulation import GameSim
            
            home_team = game_data['home_team']
            away_team = game_data['away_team']
            
            # Create and run simulation
            sim = GameSim(home_team, away_team)
            sim.run()
            
            # Store the result
            game_result = {
                'date': game_data['date'],
                'home_team': home_team,
                'away_team': away_team,
                'home_score': sim.home_score,
                'away_score': sim.away_score
            }
            
            # Add to game results
            self.parent.game_results.append(game_result)
            
            # Update team stats
            self._update_team_stats_from_game(game_result)
            
            # Show result
            tk.messagebox.showinfo("Game Simulated", 
                                 f"Game Result:\n\n"
                                 f"{away_team.team_name} {sim.away_score} - {sim.home_score} {home_team.team_name}")
                                 
        except Exception as e:
            tk.messagebox.showerror("Simulation Error", 
                                   f"Failed to simulate game:\n{str(e)}")
                                   
    def _update_team_stats_from_game(self, game_result):
        """Update team statistics from game result."""
        home_team = game_result['home_team']
        away_team = game_result['away_team']
        home_score = game_result['home_score']
        away_score = game_result['away_score']
        
        # Update games played
        home_team.games_played += 1
        away_team.games_played += 1
        
        # Update goals
        home_team.goals_for += home_score
        home_team.goals_against += away_score
        away_team.goals_for += away_score
        away_team.goals_against += home_score
        
        # Update wins/losses
        if home_score > away_score:
            home_team.wins += 1
            home_team.points += 2
            away_team.losses += 1
        elif away_score > home_score:
            away_team.wins += 1
            away_team.points += 2
            home_team.losses += 1
        else:
            # Tie - handle overtime/shootout later
            home_team.overtimes += 1
            away_team.overtimes += 1
            home_team.points += 1
            away_team.points += 1
            
        # Update goal differential
        home_team.goal_differential = home_team.goals_for - home_team.goals_against
        away_team.goal_differential = away_team.goals_for - away_team.goals_against
        
    def view_game_stats(self):
        """View detailed stats for the selected game."""
        tk.messagebox.showinfo("Game Stats", "Detailed game statistics coming soon!")
        
    def view_game_recap(self):
        """View game recap and highlights."""
        tk.messagebox.showinfo("Game Recap", "Game recap feature coming soon!")

    def update_views(self):
        self.my_schedule_tree.delete(*self.my_schedule_tree.get_children())
        self.league_schedule_tree.delete(*self.league_schedule_tree.get_children())
        
        self.schedule_data.clear()
        
        for game_entry in self.parent.league.schedule:
            # Handle different schedule formats
            if isinstance(game_entry, dict):
                # New format: dictionary with date, home_team, away_team, etc.
                game_date = game_entry['date']
                home = game_entry['home_team']
                away = game_entry['away_team']
            elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
                # Old format: tuple/list with (date, home_team, away_team)
                game_date, home, away = game_entry[0], game_entry[1], game_entry[2]
            else:
                continue  # Skip malformed entries
            
            # Determine game status and score
            status = "Scheduled"
            score = "- : -"
            
            if game_date < self.parent.current_date:
                # Look for actual game result
                for game_result in self.parent.game_results:
                    if (game_result['date'] == game_date and 
                        game_result['home_team'] == home and 
                        game_result['away_team'] == away):
                        score = f"{game_result['away_score']}-{game_result['home_score']}"
                        status = "Final"
                        break
                if status != "Final":
                    score = "0-0"  # Fallback if no result found
                    status = "Simulated"
            elif game_date == self.parent.current_date:
                status = "Today"
            
            values = (game_date.strftime("%b %d, %Y"), away.team_name, score, home.team_name, status)
            
            # Store game data for easy access
            game_key = f"{game_date}_{home.team_name}_{away.team_name}"
            self.schedule_data[game_key] = {
                'date': game_date,
                'home': home,
                'away': away,
                'score': score,
                'status': status
            }
            
            item_id = self.league_schedule_tree.insert('', 'end', values=values)
            if self.parent.user_team in (home, away):
                my_item_id = self.my_schedule_tree.insert('', 'end', values=values)
                
                # Highlight user team games
                if status == "Today":
                    self.my_schedule_tree.item(my_item_id, tags=('today',))
                elif status == "Final":
                    self.my_schedule_tree.item(my_item_id, tags=('completed',))
                    
        # Configure tags for styling
        self.my_schedule_tree.tag_configure('today', background='#4A5C2A', foreground='#FFFFFF')
        self.my_schedule_tree.tag_configure('completed', background='#2A3F5F', foreground='#CCCCCC')

class FinancesWindow(tk.Toplevel):
    """Comprehensive financial management window with detailed breakdown and projections."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(f"{parent.user_team.team_name} - Financial Management")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # Initialize data structures
        self.current_season = 2024
        self.selected_projection_year = tk.StringVar(master=self, value=str(self.current_season))
        
        # Create the interface
        self.create_interface()
        self.setup_styles()
        self.update_views()
        
        # Track window
        self.parent.open_windows['finances'] = self

    def create_interface(self):
        """Create the comprehensive financial interface."""
        # Main container
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header section
        self.create_header_section(main_container)
        
        # Main tabbed interface
        self.notebook = ttk.Notebook(main_container, style='Modern.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Salary Cap Overview tab
        self.create_salary_cap_tab()
        
        # Player Contracts tab  
        self.create_contracts_tab()
        
        # Future Projections tab
        self.create_projections_tab()
        
        # Contract Management tab
        self.create_management_tab()
        
        # Financial Reports tab
        self.create_reports_tab()

    def create_header_section(self, parent):
        """Create header with financial overview."""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame', padding=(20, 15))
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(
            header_frame,
            text=f"{self.parent.user_team.team_name.upper()} FINANCIAL MANAGEMENT",
            style='Title.TLabel',
            font=(self.parent.FONT_FAMILY, 18, 'bold')
        )
        title_label.pack(side=tk.LEFT)
        
        # Quick stats on the right
        stats_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        stats_frame.pack(side=tk.RIGHT)
        
        # Calculate current financials
        current_payroll = self.calculate_current_payroll()
        salary_cap = 83_500_000  # Current NHL salary cap
        cap_space = salary_cap - current_payroll
        
        self.header_stats_label = ttk.Label(
            stats_frame,
            text=f"Cap Space: ${cap_space:,} | Payroll: ${current_payroll:,} | Cap: ${salary_cap:,}",
            style='Header.TLabel',
            font=(self.parent.FONT_FAMILY, 12)
        )
        self.header_stats_label.pack()

    def create_salary_cap_tab(self):
        """Create salary cap overview tab."""
        cap_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        self.notebook.add(cap_frame, text="💰 Salary Cap")
        
        # Top section - Cap overview
        overview_frame = ttk.LabelFrame(cap_frame, text="Salary Cap Overview")
        overview_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create overview grid
        overview_grid = ttk.Frame(overview_frame)
        overview_grid.pack(fill=tk.X, padx=15, pady=15)
        
        # Configure grid columns
        for i in range(4):
            overview_grid.columnconfigure(i, weight=1)
        
        # Current payroll breakdown
        current_payroll = self.calculate_current_payroll()
        ahl_payroll = self.calculate_ahl_payroll()
        buried_salary = self.calculate_buried_salary()
        salary_cap = 83_500_000
        cap_space = salary_cap - current_payroll
        
        self.create_stat_box(overview_grid, "Current Payroll", f"${current_payroll:,}", 0, 0)
        self.create_stat_box(overview_grid, "Salary Cap", f"${salary_cap:,}", 0, 1)
        self.create_stat_box(overview_grid, "Cap Space", f"${cap_space:,}", 0, 2, 
                           color='green' if cap_space > 0 else 'red')
        self.create_stat_box(overview_grid, "AHL Payroll", f"${ahl_payroll:,}", 0, 3)
        
        # Cap utilization bar
        self.create_cap_utilization_bar(overview_frame, current_payroll, salary_cap)
        
        # Middle section - Position breakdown
        position_frame = ttk.LabelFrame(cap_frame, text="Salary by Position", )
        position_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create position breakdown treeview
        pos_columns = {
            'position': ('Position', 100),
            'players': ('Players', 80),
            'total_salary': ('Total Salary', 120),
            'avg_salary': ('Avg Salary', 120),
            'percentage': ('% of Cap', 80)
        }
        
        self.position_tree = self.parent._create_treeview(position_frame, pos_columns, 8)
        self.position_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_contracts_tab(self):
        """Create detailed player contracts tab."""
        contracts_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        self.notebook.add(contracts_frame, text="📋 Contracts")
        
        # Controls frame
        controls_frame = ttk.Frame(contracts_frame, style='Panel.TFrame')
        controls_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Filter controls
        filter_frame = ttk.LabelFrame(controls_frame, text="Filters", )
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Roster filter
        ttk.Label(filter_grid, text="Roster:", style='Info.TLabel').grid(row=0, column=0, padx=5, sticky='w')
        self.roster_filter = ttk.Combobox(filter_grid, values=['All', 'NHL', 'AHL', 'Prospects'], width=12)
        self.roster_filter.set('All')
        self.roster_filter.grid(row=0, column=1, padx=5)
        self.roster_filter.bind('<<ComboboxSelected>>', lambda e: self.update_contracts_view())
        
        # Position filter
        ttk.Label(filter_grid, text="Position:", style='Info.TLabel').grid(row=0, column=2, padx=5, sticky='w')
        self.position_filter = ttk.Combobox(filter_grid, values=['All', 'G', 'D', 'F'], width=12)
        self.position_filter.set('All')
        self.position_filter.grid(row=0, column=3, padx=5)
        self.position_filter.bind('<<ComboboxSelected>>', lambda e: self.update_contracts_view())
        
        # Contract status filter
        ttk.Label(filter_grid, text="Status:", style='Info.TLabel').grid(row=0, column=4, padx=5, sticky='w')
        self.status_filter = ttk.Combobox(filter_grid, values=['All', 'Expiring', 'RFA', 'UFA', 'Long-term'], width=12)
        self.status_filter.set('All')
        self.status_filter.grid(row=0, column=5, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self.update_contracts_view())
        
        # Contracts treeview
        contract_columns = {
            'name': ('Player', 180),
            'position': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'salary': ('Salary', 100),
            'years': ('Years', 60),
            'status': ('Status', 80),
            'trade_clause': ('NTC', 60),
            'cap_hit': ('Cap Hit', 100),
            'expiry': ('Expires', 70)
        }
        
        self.contracts_tree = self.parent._create_treeview(contracts_frame, contract_columns, 20)
        self.contracts_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add universal player context menu
        add_player_context_menu(self.contracts_tree, self)

    def create_projections_tab(self):
        """Create future salary projections tab."""
        projections_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        self.notebook.add(projections_frame, text="📈 Projections")
        
        # Controls
        controls_frame = ttk.Frame(projections_frame, style='Panel.TFrame')
        controls_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(controls_frame, text="View Year:", style='Info.TLabel').pack(side=tk.LEFT, padx=5)
        
        year_combo = ttk.Combobox(controls_frame, textvariable=self.selected_projection_year, 
                                 values=[str(y) for y in range(self.current_season, self.current_season + 6)], 
                                 width=10)
        year_combo.pack(side=tk.LEFT, padx=5)
        year_combo.bind('<<ComboboxSelected>>', lambda e: self.update_projections_view())
        
        # Refresh button
        ttk.Button(controls_frame, text="Refresh", command=self.update_projections_view).pack(side=tk.LEFT, padx=10)
        
        # Summary frame
        summary_frame = ttk.LabelFrame(projections_frame, text="Financial Projection Summary", )
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.projection_summary_label = ttk.Label(summary_frame, text="", font=('Consolas', 10), style='Info.TLabel')
        self.projection_summary_label.pack(padx=15, pady=15)
        
        # Expiring contracts
        expiring_frame = ttk.LabelFrame(projections_frame, text="Expiring Contracts", )
        expiring_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        expiring_columns = {
            'name': ('Player', 180),
            'position': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'salary': ('Current Salary', 120),
            'years_left': ('Years Left', 80),
            'status': ('Status', 100),
            'estimated_ask': ('Est. Ask', 120)
        }
        
        self.expiring_tree = self.parent._create_treeview(expiring_frame, expiring_columns, 15)
        self.expiring_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_management_tab(self):
        """Create contract management tools tab."""
        management_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        self.notebook.add(management_frame, text="🔧 Management")
        
        # Quick actions section
        actions_frame = ttk.LabelFrame(management_frame, text="Quick Actions", )
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill=tk.X, padx=15, pady=15)
        
        # Configure grid
        for i in range(3):
            actions_grid.columnconfigure(i, weight=1)
        
        # Action buttons
        ttk.Button(actions_grid, text="📝 Negotiate Extensions", 
                  command=self.open_contract_extensions).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        
        ttk.Button(actions_grid, text="🔄 Trade Evaluator", 
                  command=self.open_trade_evaluator).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Button(actions_grid, text="Salary Analytics", 
                  command=self.show_salary_analytics).grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        
        ttk.Button(actions_grid, text="💸 Buyout Calculator", 
                  command=self.open_buyout_calculator).grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        
        ttk.Button(actions_grid, text="🎯 Cap Compliance Check", 
                  command=self.check_cap_compliance).grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Button(actions_grid, text="📋 Export Report", 
                  command=self.export_financial_report).grid(row=1, column=2, padx=5, pady=5, sticky='ew')
        
        # Recommendations section
        recommendations_frame = ttk.LabelFrame(management_frame, text="Financial Recommendations", )
        recommendations_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.recommendations_text = tk.Text(recommendations_frame, height=15, wrap=tk.WORD,
                                          bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                          font=('Segoe UI', 10), borderwidth=0)
        
        recommendations_scroll = ttk.Scrollbar(recommendations_frame, orient="vertical", command=self.recommendations_text.yview)
        self.recommendations_text.configure(yscrollcommand=recommendations_scroll.set)
        
        self.recommendations_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        recommendations_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

    def create_reports_tab(self):
        """Create financial reports tab."""
        reports_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        self.notebook.add(reports_frame, text="Reports")
        
        # Report selection
        selection_frame = ttk.LabelFrame(reports_frame, text="Select Report", )
        selection_frame.pack(fill=tk.X, padx=10, pady=10)
        
        report_grid = ttk.Frame(selection_frame)
        report_grid.pack(fill=tk.X, padx=15, pady=15)
        
        self.report_type = tk.StringVar(master=self, value="salary_breakdown")
        
        reports = [
            ("Salary Breakdown", "salary_breakdown"),
            ("Contract Timeline", "contract_timeline"),
            ("Position Analysis", "position_analysis"),
            ("Age Demographics", "age_demographics"),
            ("Performance vs Salary", "performance_salary")
        ]
        
        for i, (text, value) in enumerate(reports):
            ttk.Radiobutton(report_grid, text=text, variable=self.report_type, value=value,
                           command=self.update_report_view).grid(row=i//3, column=i%3, padx=10, pady=5, sticky='w')
        
        # Report display
        display_frame = ttk.LabelFrame(reports_frame, text="Report Output", )
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.report_text = tk.Text(display_frame, wrap=tk.WORD,
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=('Consolas', 10), borderwidth=0)
        
        report_scroll = ttk.Scrollbar(display_frame, orient="vertical", command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scroll.set)
        
        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

    def setup_styles(self):
        """Set up custom styles for the finances window."""
        style = ttk.Style()
        
        # Modern notebook style
        style.configure('Modern.TNotebook', background=self.parent.BG_COLOR, borderwidth=0)
        style.configure('Modern.TNotebook.Tab', padding=[20, 10], font=(self.parent.FONT_FAMILY, 10))

    # Helper methods
    def create_stat_box(self, parent, title, value, row, col, color=None):
        """Create a statistical display box."""
        box_frame = ttk.Frame(parent, style='Panel.TFrame', padding=10)
        box_frame.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
        
        title_label = ttk.Label(box_frame, text=title, style='Info.TLabel', font=(self.parent.FONT_FAMILY, 10))
        title_label.pack()
        
        value_style = 'Header.TLabel'
        if color == 'green':
            value_style = 'Success.TLabel'
        elif color == 'red':
            value_style = 'Error.TLabel'
        
        value_label = ttk.Label(box_frame, text=value, style=value_style, font=(self.parent.FONT_FAMILY, 14, 'bold'))
        value_label.pack()

    def create_cap_utilization_bar(self, parent, current_payroll, salary_cap):
        """Create a visual salary cap utilization bar."""
        bar_frame = ttk.Frame(parent)
        bar_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Calculate percentage
        percentage = (current_payroll / salary_cap) * 100
        
        # Create canvas for the bar
        canvas = tk.Canvas(bar_frame, height=30, bg=self.parent.CONTENT_BG, highlightthickness=0)
        canvas.pack(fill=tk.X)
        
        # Draw the bar
        bar_width = 400
        bar_height = 20
        x_start = 10
        y_start = 5
        
        # Background bar (cap limit)
        canvas.create_rectangle(x_start, y_start, x_start + bar_width, y_start + bar_height, 
                              fill='#444444', outline='#666666')
        
        # Used cap bar
        used_width = (current_payroll / salary_cap) * bar_width
        color = '#D13438' if percentage > 95 else '#4CAF50' if percentage < 80 else '#FFA500'
        
        canvas.create_rectangle(x_start, y_start, x_start + used_width, y_start + bar_height, 
                              fill=color, outline=color)
        
        # Percentage text
        canvas.create_text(x_start + bar_width + 20, y_start + bar_height/2, 
                         text=f"{percentage:.1f}% utilized", 
                         fill=self.parent.TEXT_COLOR, anchor='w')

    # Calculation methods
    def calculate_current_payroll(self):
        """Calculate the current NHL payroll."""
        total = 0
        for player in self.parent.user_team.roster:
            if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                total += player.contract.salary
            elif hasattr(player, 'salary'):
                total += player.salary
        return total

    def calculate_ahl_payroll(self):
        """Calculate the AHL payroll."""
        total = 0
        for player in getattr(self.parent.user_team, 'ahl_roster', []):
            if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                total += player.contract.salary
            elif hasattr(player, 'salary'):
                total += player.salary
        return total

    def calculate_buried_salary(self):
        """Calculate buried salary (players in AHL making over minimum)."""
        # For now, return 0 as this requires more complex contract tracking
        return 0

    # Update methods
    def update_views(self):
        """Update all views in the finances window."""
        self.update_salary_cap_view()
        self.update_contracts_view()
        self.update_projections_view()
        self.update_recommendations()
        self.update_report_view()

    def update_salary_cap_view(self):
        """Update the salary cap overview."""
        # Update header stats
        current_payroll = self.calculate_current_payroll()
        salary_cap = 83_500_000
        cap_space = salary_cap - current_payroll
        
        self.header_stats_label.config(
            text=f"Cap Space: ${cap_space:,} | Payroll: ${current_payroll:,} | Cap: ${salary_cap:,}"
        )
        
        # Update position breakdown
        self.position_tree.delete(*self.position_tree.get_children())
        
        position_data = self.calculate_position_breakdown()
        for pos, data in position_data.items():
            percentage = (data['total'] / salary_cap) * 100 if salary_cap > 0 else 0
            values = (
                pos,
                str(data['count']),
                f"${data['total']:,}",
                f"${data['avg']:,}",
                f"{percentage:.1f}%"
            )
            self.position_tree.insert('', 'end', values=values)

    def calculate_position_breakdown(self):
        """Calculate salary breakdown by position."""
        positions = {'Goalies': {'count': 0, 'total': 0}, 
                    'Defense': {'count': 0, 'total': 0}, 
                    'Forwards': {'count': 0, 'total': 0}}
        
        for player in self.parent.user_team.roster:
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
            
            if hasattr(player, 'primary_position'):
                if player.primary_position == PlayerPosition.GOALIE:
                    positions['Goalies']['count'] += 1
                    positions['Goalies']['total'] += salary
                elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                    positions['Defense']['count'] += 1
                    positions['Defense']['total'] += salary
                else:
                    positions['Forwards']['count'] += 1
                    positions['Forwards']['total'] += salary
        
        # Calculate averages
        for pos_data in positions.values():
            pos_data['avg'] = pos_data['total'] // pos_data['count'] if pos_data['count'] > 0 else 0
        
        return positions

    def update_contracts_view(self):
        """Update the contracts view with filtering."""
        self.contracts_tree.delete(*self.contracts_tree.get_children())
        self.parent.tree_maps['contracts'].clear()
        
        # Get all players based on roster filter
        roster_filter = self.roster_filter.get()
        players = []
        
        if roster_filter == 'All':
            players.extend(self.parent.user_team.roster)
            players.extend(getattr(self.parent.user_team, 'ahl_roster', []))
            players.extend(getattr(self.parent.user_team, 'prospects', []))
        elif roster_filter == 'NHL':
            players = self.parent.user_team.roster
        elif roster_filter == 'AHL':
            players = getattr(self.parent.user_team, 'ahl_roster', [])
        elif roster_filter == 'Prospects':
            players = getattr(self.parent.user_team, 'prospects', [])
        
        # Apply filters and populate tree
        for player in players:
            # Position filter
            pos_filter = self.position_filter.get()
            if pos_filter != 'All':
                if hasattr(player, 'primary_position'):
                    if pos_filter == 'G' and player.primary_position != PlayerPosition.GOALIE:
                        continue
                    elif pos_filter == 'D' and player.primary_position not in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                        continue
                    elif pos_filter == 'F' and player.primary_position not in [PlayerPosition.CENTER, PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
                        continue
            
            # Get contract info
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            years = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            
            # Determine status
            status = self.determine_contract_status(player, years)
            
            # Status filter
            status_filter = self.status_filter.get()
            if status_filter != 'All' and status != status_filter:
                continue
            
            # Format position
            position = getattr(player.primary_position, 'name', 'F') if hasattr(player, 'primary_position') else 'F'
            if position in ['LEFT_WING', 'RIGHT_WING', 'CENTER']:
                position = position[0] if position == 'CENTER' else position[:2]
            elif position in ['LEFT_DEFENSE', 'RIGHT_DEFENSE', 'DEFENSE']:
                position = 'D'
            elif position == 'GOALIE':
                position = 'G'
            
            values = (
                player.full_name,
                position,
                str(getattr(player, 'age', 22)),
                str(player.overall_rating()),
                f"${salary:,}",
                str(years),
                status,
                ("Yes" if getattr(player.contract, 'no_trade_clause', False) else "No") if hasattr(player, 'contract') else "No",
                f"${salary:,}",  # Cap hit (simplified)
                str(self.current_season + years)
            )
            
            item = self.contracts_tree.insert('', 'end', values=values)
            self.parent.tree_maps['contracts'][item] = player

    def determine_contract_status(self, player, years_remaining):
        """Determine the contract status of a player."""
        age = getattr(player, 'age', 22)
        
        if years_remaining <= 1:
            if age < 25:
                return "RFA"
            else:
                return "UFA"
        elif years_remaining <= 2:
            return "Expiring"
        else:
            return "Long-term"

    def update_projections_view(self):
        """Update the projections view."""
        selected_year = int(self.selected_projection_year.get())
        years_ahead = selected_year - self.current_season
        
        # Calculate projected payroll
        projected_payroll = 0
        expiring_players = []
        
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            
            if years_left > years_ahead:
                projected_payroll += salary
            else:
                expiring_players.append(player)
        
        # Update summary
        salary_cap = 83_500_000  # Assume static for projection
        projected_space = salary_cap - projected_payroll
        
        summary_text = f"""
Projection for {selected_year} Season:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Committed Payroll:    ${projected_payroll:,}
Projected Cap:        ${salary_cap:,}
Available Space:      ${projected_space:,}
Expiring Contracts:   {len(expiring_players)} players
"""
        
        self.projection_summary_label.config(text=summary_text)
        
        # Update expiring contracts tree
        self.expiring_tree.delete(*self.expiring_tree.get_children())
        
        for player in expiring_players:
            estimated_ask = self.estimate_contract_ask(player)
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            current_salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            
            status = self.determine_contract_status(player, years_left)
            position = getattr(player.primary_position, 'name', 'F') if hasattr(player, 'primary_position') else 'F'
            
            values = (
                player.full_name,
                position[:1] if position in ['CENTER', 'LEFT_WING', 'RIGHT_WING'] else position[:1],
                str(getattr(player, 'age', 22)),
                str(player.overall_rating()),
                f"${current_salary:,}",
                str(years_left),
                status,
                f"${estimated_ask:,}"
            )
            
            self.expiring_tree.insert('', 'end', values=values)

    def estimate_contract_ask(self, player):
        """Estimate what a player might ask for in their next contract."""
        ovr = player.overall_rating()
        age = getattr(player, 'age', 22)
        current_salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
        
        # Base estimate on overall rating
        if ovr >= 85:
            base_ask = random.randint(8_000_000, 12_000_000)
        elif ovr >= 80:
            base_ask = random.randint(5_000_000, 8_000_000)
        elif ovr >= 75:
            base_ask = random.randint(3_000_000, 5_000_000)
        elif ovr >= 70:
            base_ask = random.randint(1_500_000, 3_000_000)
        else:
            base_ask = random.randint(750_000, 1_500_000)
        
        # Age adjustments
        if age < 25:
            base_ask *= 0.9  # Younger players more affordable
        elif age > 32:
            base_ask *= 0.8  # Older players less expensive
        
        # Don't go too far from current salary unless big performance change
        if current_salary > 0:
            max_increase = current_salary * 1.5
            min_decrease = current_salary * 0.7
            base_ask = max(min_decrease, min(max_increase, base_ask))
        
        return int(base_ask)

    def update_recommendations(self):
        """Update financial recommendations."""
        recommendations = self.generate_recommendations()
        
        self.recommendations_text.delete(1.0, tk.END)
        for rec in recommendations:
            self.recommendations_text.insert(tk.END, f"• {rec}\n\n")

    def generate_recommendations(self):
        """Generate financial recommendations based on current situation."""
        recommendations = []
        
        current_payroll = self.calculate_current_payroll()
        salary_cap = 83_500_000
        cap_space = salary_cap - current_payroll
        cap_percentage = (current_payroll / salary_cap) * 100
        
        # Cap space recommendations
        if cap_percentage > 95:
            recommendations.append("URGENT: You are very close to the salary cap. Consider trading high-salary players or demoting players to create space.")
        elif cap_percentage > 90:
            recommendations.append("WARNING: Limited cap space available. Be cautious with any new signings.")
        elif cap_percentage < 70:
            recommendations.append("You have significant cap space available. Consider upgrading your roster through free agency or trades.")
        
        # Contract expiry analysis
        expiring_next_year = []
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            if years_left <= 1:
                expiring_next_year.append(player)
        
        if len(expiring_next_year) > 8:
            recommendations.append(f"You have {len(expiring_next_year)} players with expiring contracts. Start extension negotiations early to avoid losing key players.")
        
        # Age demographics
        old_expensive_players = []
        for player in self.parent.user_team.roster:
            age = getattr(player, 'age', 22)
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            if age > 33 and salary > 4_000_000:
                old_expensive_players.append(player)
        
        if old_expensive_players:
            recommendations.append(f"Consider the future value of older, expensive players: {', '.join([p.full_name for p in old_expensive_players[:3]])}{'...' if len(old_expensive_players) > 3 else ''}")
        
        # Position balance
        position_data = self.calculate_position_breakdown()
        for pos, data in position_data.items():
            percentage = (data['total'] / current_payroll) * 100 if current_payroll > 0 else 0
            if pos == 'Goalies' and percentage > 15:
                recommendations.append("Your goalie spending is high relative to other positions. Consider if this allocation is optimal.")
            elif pos == 'Defense' and percentage > 35:
                recommendations.append("High spending on defense. Ensure this matches your team strategy.")
            elif pos == 'Forwards' and percentage < 50:
                recommendations.append("Consider if your forward spending is sufficient for offensive production.")
        
        if not recommendations:
            recommendations.append("Your financial situation looks stable. Continue monitoring contract expirations and cap space.")
        
        return recommendations

    def update_report_view(self):
        """Update the selected report view."""
        report_type = self.report_type.get()
        
        self.report_text.delete(1.0, tk.END)
        
        if report_type == "salary_breakdown":
            self.generate_salary_breakdown_report()
        elif report_type == "contract_timeline":
            self.generate_contract_timeline_report()
        elif report_type == "position_analysis":
            self.generate_position_analysis_report()
        elif report_type == "age_demographics":
            self.generate_age_demographics_report()
        elif report_type == "performance_salary":
            self.generate_performance_salary_report()

    def generate_salary_breakdown_report(self):
        """Generate detailed salary breakdown report."""
        current_payroll = self.calculate_current_payroll()
        
        report = f"""
SALARY BREAKDOWN REPORT
{self.parent.user_team.team_name} - {self.current_season} Season
{'='*60}

SUMMARY
-------
Total Payroll:    ${current_payroll:,}
Salary Cap:       ${83_500_000:,}
Cap Space:        ${83_500_000 - current_payroll:,}
Cap Utilization:  {(current_payroll / 83_500_000) * 100:.1f}%

TOP 10 SALARIES
---------------
"""
        
        # Sort players by salary
        sorted_players = sorted(self.parent.user_team.roster, 
                              key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0), 
                              reverse=True)
        
        for i, player in enumerate(sorted_players[:10], 1):
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
            percentage = (salary / current_payroll) * 100 if current_payroll > 0 else 0
            report += f"{i:2}. {player.full_name:<20} ${salary:>10,} ({percentage:4.1f}%)\n"
        
        # Position breakdown
        position_data = self.calculate_position_breakdown()
        report += "\n\nPOSITION BREAKDOWN\n------------------\n"
        
        for pos, data in position_data.items():
            percentage = (data['total'] / current_payroll) * 100 if current_payroll > 0 else 0
            report += f"{pos:<10} {data['count']:2} players  ${data['total']:>10,} ({percentage:4.1f}%) avg: ${data['avg']:,}\n"
        
        self.report_text.insert(tk.END, report)

    def generate_contract_timeline_report(self):
        """Generate contract timeline report."""
        report = f"""
CONTRACT TIMELINE REPORT
{self.parent.user_team.team_name}
{'='*50}

CONTRACTS BY EXPIRY YEAR
------------------------
"""
        
        # Group by expiry year
        expiry_groups = {}
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            expiry_year = self.current_season + years_left
            
            if expiry_year not in expiry_groups:
                expiry_groups[expiry_year] = []
            expiry_groups[expiry_year].append(player)
        
        for year in sorted(expiry_groups.keys()):
            players = expiry_groups[year]
            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)
            
            report += f"\n{year}: {len(players)} players, ${total_salary:,}\n"
            report += "-" * 40 + "\n"
            
            for player in sorted(players, key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0), reverse=True):
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                age_at_expiry = getattr(player, 'age', 22) + (year - self.current_season)
                status = "RFA" if age_at_expiry < 25 else "UFA"
                report += f"  {player.full_name:<20} ${salary:>8,} (age {age_at_expiry}, {status})\n"
        
        self.report_text.insert(tk.END, report)

    def generate_position_analysis_report(self):
        """Generate position analysis report."""
        report = f"""
POSITION ANALYSIS REPORT
{self.parent.user_team.team_name}
{'='*50}

DETAILED POSITION BREAKDOWN
---------------------------
"""
        
        # Analyze by specific positions
        positions = {
            'Goalies': [],
            'Defense': [],
            'Centers': [],
            'Wingers': []
        }
        
        for player in self.parent.user_team.roster:
            if hasattr(player, 'primary_position'):
                if player.primary_position == PlayerPosition.GOALIE:
                    positions['Goalies'].append(player)
                elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                    positions['Defense'].append(player)
                elif player.primary_position == PlayerPosition.CENTER:
                    positions['Centers'].append(player)
                else:
                    positions['Wingers'].append(player)
        
        for pos_name, players in positions.items():
            if not players:
                continue
                
            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)
            avg_salary = total_salary / len(players) if players else 0
            avg_age = sum(getattr(p, 'age', 22) for p in players) / len(players) if players else 0
            avg_ovr = sum(p.overall_rating() for p in players) / len(players) if players else 0
            
            report += f"\n{pos_name.upper()}\n"
            report += f"Players: {len(players)}\n"
            report += f"Total Salary: ${total_salary:,}\n"
            report += f"Average Salary: ${avg_salary:,.0f}\n"
            report += f"Average Age: {avg_age:.1f}\n"
            report += f"Average OVR: {avg_ovr:.1f}\n"
            report += "-" * 30 + "\n"
            
            for player in sorted(players, key=lambda p: getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0), reverse=True):
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                report += f"  {player.full_name:<20} {getattr(player, 'age', 22):2} yrs  OVR {player.overall_rating():2}  ${salary:>8,}\n"
        
        self.report_text.insert(tk.END, report)

    def generate_age_demographics_report(self):
        """Generate age demographics report."""
        report = f"""
AGE DEMOGRAPHICS REPORT
{self.parent.user_team.team_name}
{'='*50}

AGE GROUP BREAKDOWN
-------------------
"""
        
        age_groups = {
            '18-22': [], '23-26': [], '27-30': [], '31-34': [], '35+': []
        }
        
        for player in self.parent.user_team.roster:
            age = getattr(player, 'age', 22)
            if age <= 22:
                age_groups['18-22'].append(player)
            elif age <= 26:
                age_groups['23-26'].append(player)
            elif age <= 30:
                age_groups['27-30'].append(player)
            elif age <= 34:
                age_groups['31-34'].append(player)
            else:
                age_groups['35+'].append(player)
        
        for group_name, players in age_groups.items():
            if not players:
                continue
                
            total_salary = sum(getattr(p.contract, 'salary', 0) if hasattr(p, 'contract') else getattr(p, 'salary', 0) for p in players)
            avg_ovr = sum(p.overall_rating() for p in players) / len(players) if players else 0
            
            report += f"\nAGE {group_name}\n"
            report += f"Players: {len(players)}\n"
            report += f"Total Salary: ${total_salary:,}\n"
            report += f"Average OVR: {avg_ovr:.1f}\n"
            report += "-" * 25 + "\n"
            
            for player in players:
                salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
                report += f"  {player.full_name:<20} {getattr(player, 'age', 22):2} yrs  ${salary:>8,}\n"
        
        self.report_text.insert(tk.END, report)

    def generate_performance_salary_report(self):
        """Generate performance vs salary analysis."""
        report = f"""
PERFORMANCE vs SALARY ANALYSIS
{self.parent.user_team.team_name}
{'='*50}

VALUE ANALYSIS
--------------
(Players ranked by value: OVR rating vs salary cost)
"""
        
        # Calculate value scores
        player_values = []
        for player in self.parent.user_team.roster:
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 0)
            ovr = player.overall_rating()
            
            # Calculate value score (higher is better value)
            if salary > 0:
                value_score = (ovr ** 2) / (salary / 1_000_000)  # OVR squared divided by salary in millions
            else:
                value_score = ovr ** 2
            
            player_values.append((player, ovr, salary, value_score))
        
        # Sort by value score
        player_values.sort(key=lambda x: x[3], reverse=True)
        
        report += "\nBEST VALUE CONTRACTS\n" + "-" * 25 + "\n"
        for i, (player, ovr, salary, value) in enumerate(player_values[:10], 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"
        
        report += "\nHIGHEST PAID PLAYERS\n" + "-" * 25 + "\n"
        highest_paid = sorted(player_values, key=lambda x: x[2], reverse=True)[:10]
        for i, (player, ovr, salary, value) in enumerate(highest_paid, 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"
        
        report += "\nPOTENTIAL OVERPAYS\n" + "-" * 25 + "\n"
        potential_overpays = [pv for pv in player_values if pv[2] > 3_000_000 and pv[3] < 50][:5]
        for i, (player, ovr, salary, value) in enumerate(potential_overpays, 1):
            report += f"{i:2}. {player.full_name:<20} OVR {ovr:2} ${salary:>8,} (Value: {value:.1f})\n"
        
        self.report_text.insert(tk.END, report)

    # Event handlers
    def _show_contracts_context_menu(self, event):
        """Show context menu for contract-specific options"""
        if hasattr(self, 'contracts_tree'):
            selection = self.contracts_tree.selection()
            if selection:
                player = self.parent.tree_maps.get(self.contracts_tree, {}).get(selection[0])
                if player:
                    # Create context menu with contract options
                    context_menu = PlayerContextMenu(self)
                    context_menu.add_separator()
                    context_menu.add_command("Negotiate Extension", lambda p=player: self.negotiate_extension())
                    context_menu.add_command("Trade Player", lambda p=player: self.trade_player())
                    context_menu.add_command("Contract Details", lambda p=player: self._view_contract_details(p))
                    context_menu.show_context_menu(event, player)

    def view_contract_player_profile(self):
        """View the selected player's profile."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps['contracts']:
            player = self.parent.tree_maps['contracts'][selection[0]]
            self.parent.open_player_profile(player)

    def negotiate_extension(self):
        """Open contract negotiation for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps['contracts']:
            player = self.parent.tree_maps['contracts'][selection[0]]
            # Open contract negotiation window
            if 'contract_negotiation' not in self.parent.open_windows or not self.parent.open_windows['contract_negotiation'].winfo_exists():
                self.parent.open_windows['contract_negotiation'] = ContractNegotiationWindow(self.parent, player, is_extension=True)
            self.parent.open_windows['contract_negotiation'].focus_set()

    def trade_player(self):
        """Open trade window for selected player."""
        selection = self.contracts_tree.selection()
        if selection and selection[0] in self.parent.tree_maps['contracts']:
            player = self.parent.tree_maps['contracts'][selection[0]]
            # Open trade window with this player pre-selected
            self.parent.open_trade_window()

    # Action methods  
    def open_contract_extensions(self):
        """Open contract extensions window."""
        if 'contract_extensions' not in self.parent.open_windows or not self.parent.open_windows['contract_extensions'].winfo_exists():
            self.parent.open_windows['contract_extensions'] = ContractExtensionsWindow(self.parent)
        self.parent.open_windows['contract_extensions'].focus_set()

    def open_trade_evaluator(self):
        """Open trade evaluator tool."""
        messagebox.showinfo("Coming Soon", "Trade Evaluator tool is coming in a future update!")

    def show_salary_analytics(self):
        """Show advanced salary analytics."""
        messagebox.showinfo("Coming Soon", "Advanced Salary Analytics is coming in a future update!")

    def open_buyout_calculator(self):
        """Open buyout calculator."""
        messagebox.showinfo("Coming Soon", "Buyout Calculator is coming in a future update!")

    def check_cap_compliance(self):
        """Check salary cap compliance."""
        current_payroll = self.calculate_current_payroll()
        salary_cap = 83_500_000
        
        if current_payroll > salary_cap:
            over_amount = current_payroll - salary_cap
            messagebox.showerror("Cap Violation", f"Your team is ${over_amount:,} over the salary cap!\nYou must make moves to become compliant.")
        else:
            space = salary_cap - current_payroll
            messagebox.showinfo("Cap Compliant", f"Your team is cap compliant with ${space:,} in available space.")

    def export_financial_report(self):
        """Export detailed financial report to file."""
        try:
            from datetime import datetime
            import os
            
            # Create exports directory if it doesn't exist
            exports_dir = "exports"
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"financial_report_{self.parent.user_team.team_name.replace(' ', '_')}_{timestamp}.txt"
            filepath = os.path.join(exports_dir, filename)
            
            # Calculate financial data
            current_payroll = sum(getattr(p.contract, 'salary', getattr(p, 'salary', 750000)) 
                                for p in self.parent.user_team.roster 
                                if hasattr(p, 'contract') or hasattr(p, 'salary'))
            
            salary_cap = 83_500_000
            cap_space = salary_cap - current_payroll
            
            # Generate detailed report
            report_content = f"""
DETAILED FINANCIAL REPORT
{self.parent.user_team.team_name} - {datetime.now().strftime('%Y-%m-%d')}
{'='*70}

SALARY CAP SUMMARY
------------------
Total Payroll:      ${current_payroll:,}
Salary Cap:         ${salary_cap:,}
Available Space:    ${cap_space:,}
Cap Utilization:    {(current_payroll / salary_cap) * 100:.1f}%
Cap Status:         {'COMPLIANT' if current_payroll <= salary_cap else 'OVER CAP'}

ROSTER BREAKDOWN
----------------
"""
            
            # Sort players by salary for detailed breakdown
            sorted_players = sorted(self.parent.user_team.roster, 
                                  key=lambda p: getattr(p.contract, 'salary', getattr(p, 'salary', 750000)), 
                                  reverse=True)
            
            for i, player in enumerate(sorted_players, 1):
                salary = getattr(player.contract, 'salary', getattr(player, 'salary', 750000))
                years_left = getattr(player.contract, 'years_remaining', 0) if hasattr(player, 'contract') else 0
                
                report_content += f"{i:2d}. {player.full_name:<25} {str(player.primary_position):<8} ${salary:>10,} ({years_left} yrs)\n"
            
            # Contract expiry analysis
            report_content += f"\n\nCONTRACT EXPIRY ANALYSIS\n{'-'*25}\n"
            
            expiring_this_year = [p for p in self.parent.user_team.roster 
                                if hasattr(p, 'contract') and getattr(p.contract, 'years_remaining', 0) <= 1]
            expiring_next_year = [p for p in self.parent.user_team.roster 
                                if hasattr(p, 'contract') and getattr(p.contract, 'years_remaining', 0) == 2]
            
            report_content += f"Contracts expiring this season: {len(expiring_this_year)}\n"
            for player in expiring_this_year:
                salary = getattr(player.contract, 'salary', 750000)
                report_content += f"  • {player.full_name} - ${salary:,}\n"
            
            report_content += f"\nContracts expiring next season: {len(expiring_next_year)}\n"
            for player in expiring_next_year:
                salary = getattr(player.contract, 'salary', 750000)
                report_content += f"  • {player.full_name} - ${salary:,}\n"
            
            # Position breakdown
            report_content += f"\n\nSALARY BY POSITION\n{'-'*18}\n"
            
            position_totals = {}
            for player in self.parent.user_team.roster:
                pos = str(player.primary_position)
                salary = getattr(player.contract, 'salary', getattr(player, 'salary', 750000))
                
                if pos not in position_totals:
                    position_totals[pos] = {'total': 0, 'count': 0}
                position_totals[pos]['total'] += salary
                position_totals[pos]['count'] += 1
            
            for pos, data in sorted(position_totals.items()):
                avg_salary = data['total'] / data['count'] if data['count'] > 0 else 0
                report_content += f"{pos:<12} {data['count']:2d} players  ${data['total']:>10,}  (avg: ${avg_salary:,.0f})\n"
            
            # Future projections
            report_content += f"\n\nFUTURE CAP PROJECTIONS\n{'-'*22}\n"
            report_content += f"Next season cap space (estimated): ${cap_space:,}\n"
            report_content += f"Extension priorities: {len(expiring_this_year)} players need new contracts\n"
            report_content += f"Trade candidates: Players with high salaries and declining performance\n"
            
            # Write report to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            messagebox.showinfo("Export Successful", 
                              f"Financial report exported successfully!\n\n"
                              f"File: {filename}\n"
                              f"Location: {exports_dir}")
                              
        except Exception as e:
            print(f"Error exporting financial report: {e}")
            messagebox.showerror("Export Error", f"Failed to export financial report:\n{str(e)}")
    
    def _view_contract_details(self, player):
        """View detailed contract information"""
        contract = getattr(player, 'contract', None)
        if contract:
            salary = getattr(contract, 'salary', 750000)
            years = getattr(contract, 'years_remaining', 0)
            messagebox.showinfo("Contract Details", 
                              f"Player: {player.full_name}\n"
                              f"Salary: ${salary:,}\n"
                              f"Years remaining: {years}\n"
                              f"Cap hit: ${salary:,}")
        else:
            messagebox.showinfo("Contract Details", f"No contract information available for {player.full_name}")

class ContractExtensionsWindow(tk.Toplevel):
    """Window for managing contract extensions and negotiations."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(f"{parent.user_team.team_name} - Contract Extensions")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1000x700")
        
        self.create_interface()
        self.update_views()
        
        # Track window
        self.parent.open_windows['contract_extensions'] = self

    def create_interface(self):
        """Create the contract extensions interface."""
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header
        header_label = ttk.Label(main_frame, text="CONTRACT EXTENSIONS", 
                                style='Title.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        header_label.pack(pady=(0, 20))
        
        # Eligible players frame
        eligible_frame = ttk.LabelFrame(main_frame, text="Extension Eligible Players", )
        eligible_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create treeview for eligible players
        columns = {
            'name': ('Player', 180),
            'position': ('Pos', 50),
            'age': ('Age', 50),
            'ovr': ('OVR', 50),
            'current_salary': ('Current Salary', 120),
            'years_left': ('Years Left', 80),
            'status': ('Status', 100),
            'actions': ('Actions', 120)
        }
        
        self.eligible_tree = self.parent._create_treeview(eligible_frame, columns, 15)
        self.eligible_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Store player mapping
        self.parent.tree_maps['extensions'] = {}
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(buttons_frame, text="Negotiate Extension", 
                  command=self.negotiate_selected_extension).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(buttons_frame, text="Refresh", 
                  command=self.update_views).pack(side=tk.LEFT, padx=5)

    def update_views(self):
        """Update the extensions view."""
        self.eligible_tree.delete(*self.eligible_tree.get_children())
        self.parent.tree_maps['extensions'].clear()
        
        # Find players eligible for extensions (within 2 years of expiry)
        eligible_players = []
        
        for player in self.parent.user_team.roster:
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            if years_left <= 2:  # Eligible if 2 years or less remaining
                eligible_players.append(player)
        
        # Sort by years remaining (most urgent first)
        eligible_players.sort(key=lambda p: getattr(p.contract, 'years_remaining', 1) if hasattr(p, 'contract') else 1)
        
        for player in eligible_players:
            salary = getattr(player.contract, 'salary', 0) if hasattr(player, 'contract') else getattr(player, 'salary', 750000)
            years_left = getattr(player.contract, 'years_remaining', 1) if hasattr(player, 'contract') else 1
            age = getattr(player, 'age', 22)
            
            # Determine status
            if years_left <= 1:
                if age < 25:
                    status = "RFA - Expiring"
                else:
                    status = "UFA - Expiring"
            else:
                status = "Extension Eligible"
            
            # Format position
            position = getattr(player.primary_position, 'name', 'F') if hasattr(player, 'primary_position') else 'F'
            if position in ['LEFT_WING', 'RIGHT_WING', 'CENTER']:
                position = position[0] if position == 'CENTER' else position[:2]
            elif position in ['LEFT_DEFENSE', 'RIGHT_DEFENSE', 'DEFENSE']:
                position = 'D'
            elif position == 'GOALIE':
                position = 'G'
            
            values = (
                player.full_name,
                position,
                str(age),
                str(player.overall_rating()),
                f"${salary:,}",
                str(years_left),
                status,
                "Available"
            )
            
            item = self.eligible_tree.insert('', 'end', values=values)
            self.parent.tree_maps['extensions'][item] = player

    def negotiate_selected_extension(self):
        """Negotiate extension with selected player."""
        selection = self.eligible_tree.selection()
        if selection and selection[0] in self.parent.tree_maps['extensions']:
            player = self.parent.tree_maps['extensions'][selection[0]]
            
            # Open contract negotiation window
            if 'contract_negotiation' not in self.parent.open_windows or not self.parent.open_windows['contract_negotiation'].winfo_exists():
                self.parent.open_windows['contract_negotiation'] = ContractNegotiationWindow(self.parent, player, is_extension=True)
            self.parent.open_windows['contract_negotiation'].focus_set()
        else:
            messagebox.showwarning("No Selection", "Please select a player to negotiate with.")

class NewsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("League News")
        self.geometry("800x600")
        self.configure(background='#1E1E1E')

        news_text = tk.Text(self, wrap='word', bg='#2D2D30', fg='#CCCCCC', font=('Segoe UI', 10), borderwidth=0)
        news_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        for item in reversed(parent.news_log):
            news_text.insert('1.0', f"({item['date'].strftime('%b %d')}) {item['story']}\n\n")
            
        news_text.config(state='disabled')

class GMOptionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("General Manager Options")
        self.geometry("600x450")
        self.configure(background='#1E1E1E')
        
        # GM Management Options
        management_frame = ttk.LabelFrame(self, text="Team Management", padding=15)
        management_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Button(management_frame, text="Manage Trade Block", command=self.parent.open_trade_block_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Handle Waivers", command=self.parent.open_waivers_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Set Captains", command=self.parent.open_set_captains_window).pack(pady=5, fill='x')
        ttk.Button(management_frame, text="Negotiate Extensions", command=self.negotiate_extensions).pack(pady=5, fill='x')
        
        # Game Settings & Preferences
        settings_frame = ttk.LabelFrame(self, text="Game Settings & Preferences", padding=15)
        settings_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Button(settings_frame, text="⚙️ Settings & Preferences", command=self.parent.open_settings_window).pack(pady=5, fill='x')
        
        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=20)

    def negotiate_extensions(self):
        if 'contract_extensions' not in self.parent.open_windows or not self.parent.open_windows['contract_extensions'].winfo_exists():
            self.parent.open_windows['contract_extensions'] = ContractExtensionsWindow(self.parent)
        self.parent.open_windows['contract_extensions'].focus_set()

class ContractNegotiationWindow(tk.Toplevel):
    def __init__(self, parent, player, is_extension=False):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.is_extension = is_extension
        self.title(f"Negotiate with {player.full_name}")
        self.geometry("500x450")
        self.configure(background=parent.BG_COLOR)
        self.transient(parent)
        self.grab_set()

        # Create main container with padding
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title section
        title_text = "Contract Extension" if is_extension else "Contract Offer"
        ttk.Label(main_frame, text=title_text, style='Title.TLabel').pack(pady=(0, 10))
        
        # Player info section
        player_frame = ttk.LabelFrame(main_frame, text="Player Information", style='Panel.TLabelframe')
        player_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(player_frame, text=f"Name: {player.full_name}", style='TLabel').pack(anchor='w', padx=10, pady=5)
        ttk.Label(player_frame, text=f"Position: {player.primary_position.value}", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Age: {player.age}", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Overall Rating: {player.overall_rating()}/20", style='TLabel').pack(anchor='w', padx=10, pady=2)
        ttk.Label(player_frame, text=f"Potential: {player.potential_grade}", style='TLabel').pack(anchor='w', padx=10, pady=(2, 10))
        
        # Current contract info (if extension)
        if is_extension and hasattr(player, 'salary'):
            current_frame = ttk.LabelFrame(main_frame, text="Current Contract", style='Panel.TLabelframe')
            current_frame.pack(fill='x', pady=(0, 15))
            
            ttk.Label(current_frame, text=f"Current Salary: ${player.salary:,}", style='TLabel').pack(anchor='w', padx=10, pady=5)
            if hasattr(player, 'contract_years'):
                ttk.Label(current_frame, text=f"Years Remaining: {player.contract_years}", style='TLabel').pack(anchor='w', padx=10, pady=(2, 10))
        
        # Contract offer section
        offer_frame = ttk.LabelFrame(main_frame, text="Contract Offer", style='Panel.TLabelframe')
        offer_frame.pack(fill='x', pady=(0, 15))
        
        # Salary input
        salary_frame = ttk.Frame(offer_frame)
        salary_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(salary_frame, text="Annual Salary: $", style='TLabel').pack(side='left')
        self.salary_var = tk.StringVar(master=self, value="750000")
        salary_entry = ttk.Entry(salary_frame, textvariable=self.salary_var, width=15)
        salary_entry.pack(side='left', padx=(5, 0))
        
        # Years input
        years_frame = ttk.Frame(offer_frame)
        years_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Label(years_frame, text="Contract Length:", style='TLabel').pack(side='left')
        self.years_var = tk.StringVar(master=self, value="1")
        years_entry = ttk.Entry(years_frame, textvariable=self.years_var, width=5)
        years_entry.pack(side='left', padx=(5, 5))
        ttk.Label(years_frame, text="years", style='TLabel').pack(side='left')
        
        # Total value display
        self.total_label = ttk.Label(offer_frame, text="Total Contract Value: $0", style='Subtitle.TLabel')
        self.total_label.pack(anchor='w', padx=10, pady=(10, 15))
        
        # Update total when values change
        self.salary_var.trace('w', self.update_total)
        self.years_var.trace('w', self.update_total)
        self.update_total()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=20)
        
        ttk.Button(button_frame, text="Submit Offer", command=self.submit_offer, style='TButton').pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.destroy, style='TButton').pack(side='right')

    def update_total(self, *args):
        """Update the total contract value display."""
        try:
            salary = int(self.salary_var.get().replace(',', ''))
            years = int(self.years_var.get())
            total = salary * years
            self.total_label.config(text=f"Total Contract Value: ${total:,}")
        except (ValueError, AttributeError):
            self.total_label.config(text="Total Contract Value: $0")

    def submit_offer(self):
        try:
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = int(self.years_var.get())
            
            # Validate inputs
            if salary <= 0:
                messagebox.showerror("Invalid Input", "Salary must be greater than $0.")
                return
            if years <= 0 or years > 8:
                messagebox.showerror("Invalid Input", "Contract length must be between 1 and 8 years.")
                return
            
            # Set the values on the player object first
            self.player.salary = salary
            self.player.contract_years = years
            
            # Then call handle_contract_offer with proper arguments
            accepted = self.parent.handle_contract_offer(self.player, extension=self.is_extension)
            if accepted:
                self.destroy()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for salary and years.")

class TradeBlockWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Trade Block")
        self.geometry("1200x800")
        self.configure(background=parent.BG_COLOR)
        
        # Initialize data
        self.trade_block_players = []
        self.interested_teams = {}
        
        self.create_widgets()
        self.load_trade_block()
    
    def create_widgets(self):
        """Create the trade block interface."""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Trade Block", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Create notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)
        
        # Your Trade Block tab
        self.your_block_frame = ttk.Frame(notebook)
        notebook.add(self.your_block_frame, text="Your Trade Block")
        self.create_your_trade_block(self.your_block_frame)
        
        # Other Teams' Blocks tab
        self.other_blocks_frame = ttk.Frame(notebook)
        notebook.add(self.other_blocks_frame, text="Other Teams")
        self.create_other_trade_blocks(self.other_blocks_frame)
        
        # Trade Interest tab
        self.interest_frame = ttk.Frame(notebook)
        notebook.add(self.interest_frame, text="Trade Interest")
        self.create_trade_interest(self.interest_frame)
    
    def create_your_trade_block(self, parent):
        """Create your team's trade block management."""
        # Controls frame
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(controls_frame, text="Add Player to Block", 
                  command=self.add_to_trade_block).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Remove from Block", 
                  command=self.remove_from_trade_block).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Generate Interest", 
                  command=self.generate_trade_interest).pack(side='left', padx=5)
        
        # Trade block players list
        block_frame = ttk.LabelFrame(parent, text="Players on Trade Block")
        block_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview for trade block players
        columns = ('Name', 'Position', 'Age', 'Overall', 'Salary', 'Years Left', 'Interest Level')
        self.block_tree = ttk.Treeview(block_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.block_tree.heading(col, text=col)
            if col == 'Name':
                self.block_tree.column(col, width=150)
            elif col in ['Position', 'Age', 'Overall']:
                self.block_tree.column(col, width=80)
            elif col == 'Salary':
                self.block_tree.column(col, width=120)
            else:
                self.block_tree.column(col, width=100)
        
        # Scrollbar for trade block
        block_scrollbar = ttk.Scrollbar(block_frame, orient='vertical', command=self.block_tree.yview)
        self.block_tree.configure(yscrollcommand=block_scrollbar.set)
        
        self.block_tree.pack(side='left', fill='both', expand=True)
        block_scrollbar.pack(side='right', fill='y')
        add_player_context_menu(self.block_tree, self)
    
    def create_other_trade_blocks(self, parent):
        """Create view of other teams' trade blocks."""
        # Team selection
        select_frame = ttk.Frame(parent)
        select_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(select_frame, text="Select Team:").pack(side='left', padx=5)
        self.team_var = tk.StringVar(master=self)
        self.team_combo = ttk.Combobox(select_frame, textvariable=self.team_var, 
                                      values=self.get_other_teams(), width=30)
        self.team_combo.pack(side='left', padx=5)
        self.team_combo.bind('<<ComboboxSelected>>', self.on_team_selected)
        
        ttk.Button(select_frame, text="Refresh", 
                  command=self.refresh_other_blocks).pack(side='left', padx=10)
        
        # Other teams' players
        other_frame = ttk.LabelFrame(parent, text="Available Players")
        other_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Team', 'Name', 'Position', 'Age', 'Overall', 'Salary', 'Interest')
        self.other_tree = ttk.Treeview(other_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.other_tree.heading(col, text=col)
            if col in ['Name', 'Team']:
                self.other_tree.column(col, width=120)
            elif col in ['Position', 'Age', 'Overall']:
                self.other_tree.column(col, width=80)
            else:
                self.other_tree.column(col, width=100)
        
        # Double-click to show interest
        self.other_tree.bind('<Double-1>', self.express_interest)
        
        other_scrollbar = ttk.Scrollbar(other_frame, orient='vertical', command=self.other_tree.yview)
        self.other_tree.configure(yscrollcommand=other_scrollbar.set)
        
        self.other_tree.pack(side='left', fill='both', expand=True)
        other_scrollbar.pack(side='right', fill='y')
    
    def create_trade_interest(self, parent):
        """Create trade interest management."""
        # Interest summary
        summary_frame = ttk.LabelFrame(parent, text="Trade Interest Summary")
        summary_frame.pack(fill='x', padx=10, pady=10)
        
        self.interest_summary = tk.Text(summary_frame, height=6, wrap='word', bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR, insertbackground=self.parent.TEXT_COLOR)
        self.interest_summary.pack(fill='x', padx=10, pady=10)
        
        # Detailed interest
        detail_frame = ttk.LabelFrame(parent, text="Detailed Interest")
        detail_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Your Player', 'Interested Team', 'Their Interest', 'Your Interest', 'Status')
        self.interest_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.interest_tree.heading(col, text=col)
            self.interest_tree.column(col, width=150)
        
        # Buttons for interest management
        interest_buttons = ttk.Frame(detail_frame)
        interest_buttons.pack(fill='x', pady=5)
        
        ttk.Button(interest_buttons, text="Negotiate Trade", 
                  command=self.start_trade_negotiation).pack(side='left', padx=5)
        ttk.Button(interest_buttons, text="Decline Interest", 
                  command=self.decline_interest).pack(side='left', padx=5)
        
        interest_scrollbar = ttk.Scrollbar(detail_frame, orient='vertical', command=self.interest_tree.yview)
        self.interest_tree.configure(yscrollcommand=interest_scrollbar.set)
        
        self.interest_tree.pack(side='left', fill='both', expand=True)
        interest_scrollbar.pack(side='right', fill='y')
    
    def load_trade_block(self):
        """Load current trade block data."""
        # Initialize trade block if it doesn't exist
        if not hasattr(self.parent.user_team, 'trade_block'):
            self.parent.user_team.trade_block = []
        
        self.update_trade_block_display()
        self.update_interest_display()
    
    def add_to_trade_block(self):
        """Add a player to the trade block."""
        # Create player selection dialog
        self.create_player_selection_dialog()
    
    def create_player_selection_dialog(self):
        """Create dialog to select players for trade block."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Player to Trade Block")
        dialog.geometry("600x400")
        dialog.configure(background=self.parent.BG_COLOR)
        
        # Available players
        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="Select players to add to trade block:", 
                 style='Title.TLabel').pack(pady=10)
        
        # Player list
        columns = ('Name', 'Position', 'Age', 'Overall', 'Salary')
        player_tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            player_tree.heading(col, text=col)
            player_tree.column(col, width=120)
        
        # Populate with roster players not already on trade block
        current_block = getattr(self.parent.user_team, 'trade_block', [])
        for player in self.parent.user_team.roster:
            if player not in current_block:
                salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
                player_tree.insert('', 'end', values=(
                    player.full_name,
                    str(player.primary_position),
                    player.age,
                    player.overall_rating(),
                    f"${salary:,}"
                ))
        
        player_tree.pack(fill='both', expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=10)
        
        def add_selected():
            selection = player_tree.selection()
            if selection:
                for item in selection:
                    player_name = player_tree.item(item)['values'][0]
                    player = next((p for p in self.parent.user_team.roster if p.full_name == player_name), None)
                    if player:
                        if not hasattr(self.parent.user_team, 'trade_block'):
                            self.parent.user_team.trade_block = []
                        if player not in self.parent.user_team.trade_block:
                            self.parent.user_team.trade_block.append(player)
                
                self.update_trade_block_display()
                dialog.destroy()
        
        ttk.Button(btn_frame, text="Add Selected", command=add_selected).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def remove_from_trade_block(self):
        """Remove selected player from trade block."""
        selection = self.block_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a player to remove.")
            return
        
        for item in selection:
            player_name = self.block_tree.item(item)['values'][0]
            player = next((p for p in getattr(self.parent.user_team, 'trade_block', []) 
                          if p.full_name == player_name), None)
            if player:
                self.parent.user_team.trade_block.remove(player)
        
        self.update_trade_block_display()
    
    def generate_trade_interest(self):
        """Generate interest from other teams."""
        if not hasattr(self.parent.user_team, 'trade_block') or not self.parent.user_team.trade_block:
            tk.messagebox.showinfo("No Players", "Add players to your trade block first.")
            return
        
        import random
        
        # Generate interest for each player on trade block
        for player in self.parent.user_team.trade_block:
            # Random teams might be interested
            interested_teams = random.sample(self.parent.league.teams, random.randint(1, 4))
            for team in interested_teams:
                if team != self.parent.user_team:
                    if player not in self.interested_teams:
                        self.interested_teams[player] = []
                    
                    interest_level = random.choice(['Low', 'Medium', 'High'])
                    self.interested_teams[player].append({
                        'team': team,
                        'interest_level': interest_level,
                        'status': 'Active'
                    })
        
        self.update_interest_display()
        tk.messagebox.showinfo("Interest Generated", "Trade interest has been generated for your players!")
    
    def update_trade_block_display(self):
        """Update the trade block display."""
        # Clear current items
        for item in self.block_tree.get_children():
            self.block_tree.delete(item)
        
        # Add trade block players
        trade_block = getattr(self.parent.user_team, 'trade_block', [])
        for player in trade_block:
            salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
            years_left = getattr(player.contract, 'years_remaining', 0) if player.contract else 0
            
            # Calculate interest level
            interest_count = len(self.interested_teams.get(player, []))
            if interest_count == 0:
                interest_level = "None"
            elif interest_count <= 2:
                interest_level = "Low"
            elif interest_count <= 4:
                interest_level = "Medium"
            else:
                interest_level = "High"
            
            self.block_tree.insert('', 'end', values=(
                player.full_name,
                str(player.primary_position),
                player.age,
                player.overall_rating(),
                f"${salary:,}",
                years_left,
                interest_level
            ))
    
    def update_interest_display(self):
        """Update the interest display."""
        # Clear current items
        for item in self.interest_tree.get_children():
            self.interest_tree.delete(item)
        
        # Update summary
        total_players = len(getattr(self.parent.user_team, 'trade_block', []))
        total_interest = sum(len(interests) for interests in self.interested_teams.values())
        
        summary_text = f"Players on Trade Block: {total_players}\n"
        summary_text += f"Total Interest Expressions: {total_interest}\n"
        summary_text += f"Active Negotiations: 0\n"  # Would track actual negotiations
        
        self.interest_summary.delete(1.0, tk.END)
        self.interest_summary.insert(1.0, summary_text)
        
        # Add detailed interest
        for player, interests in self.interested_teams.items():
            for interest in interests:
                self.interest_tree.insert('', 'end', values=(
                    player.full_name,
                    interest['team'].team_name,
                    interest['interest_level'],
                    "Considering",  # Your interest level
                    interest['status']
                ))
    
    def get_other_teams(self):
        """Get list of other teams."""
        return [team.team_name for team in self.parent.league.teams 
                if team != self.parent.user_team]
    
    def on_team_selected(self, event=None):
        """Handle team selection."""
        # Would populate with selected team's trade block
        # For now, show placeholder
        selected_team = self.team_var.get()
        if selected_team:
            # Clear and show message
            for item in self.other_tree.get_children():
                self.other_tree.delete(item)
            
            # Find team and show some players as "available"
            team = next((t for t in self.parent.league.teams if t.team_name == selected_team), None)
            if team:
                import random
                available_players = random.sample(team.roster, min(5, len(team.roster)))
                for player in available_players:
                    salary = getattr(player.contract, 'salary', 750000) if player.contract else 750000
                    self.other_tree.insert('', 'end', values=(
                        team.team_name,
                        player.full_name,
                        str(player.primary_position),
                        player.age,
                        player.overall_rating(),
                        f"${salary:,}",
                        random.choice(['Available', 'Limited Interest', 'High Price'])
                    ))
    
    def refresh_other_blocks(self):
        """Refresh other teams' trade blocks."""
        self.on_team_selected()
    
    def express_interest(self, event=None):
        """Express interest in a player."""
        selection = self.other_tree.selection()
        if selection:
            item = selection[0]
            values = self.other_tree.item(item)['values']
            team_name, player_name = values[0], values[1]
            
            tk.messagebox.showinfo("Interest Expressed", 
                                 f"You have expressed interest in {player_name} from {team_name}.\n\n"
                                 f"The team will consider your interest and may respond with trade proposals.")
    
    def start_trade_negotiation(self):
        """Start trade negotiation."""
        selection = self.interest_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select an interest to negotiate.")
            return
        
        values = self.interest_tree.item(selection[0])['values']
        player_name, team_name = values[0], values[1]
        
        tk.messagebox.showinfo("Trade Negotiation", 
                             f"Starting trade negotiation for {player_name} with {team_name}.\n\n"
                             f"This would open the trade negotiation interface.")
    
    def decline_interest(self):
        """Decline trade interest."""
        selection = self.interest_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select an interest to decline.")
            return
        
        # Remove from interest tracking
        self.interest_tree.delete(selection[0])
        tk.messagebox.showinfo("Interest Declined", "Trade interest has been declined.")

class WaiversWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Waivers")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(instruction_frame, text="Waiver Wire Management", font=(parent.FONT_FAMILY, 16, 'bold'), 
                 style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        ttk.Label(instruction_frame, text="Players must clear waivers when being sent down to the AHL if they have played " 
                                         "more than 160 NHL games, or are older than 25 years. "
                                         "Players on waivers can be claimed by other teams (starting with the lowest ranked team).", 
                 wraplength=900, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Create tabs
        my_players_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        waiver_wire_frame = ttk.Frame(self.notebook, style='Tab.TFrame')
        
        self.notebook.add(my_players_frame, text="Waiver-Eligible Players")
        self.notebook.add(waiver_wire_frame, text="Waiver Wire")
        
        # My players tab
        columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                  'ovr': ('OVR', 50), 'games': ('NHL Games', 80), 
                  'salary': ('Salary', 100), 'actions': ('Actions', 150)}
        
        self.eligible_tree = parent._create_treeview(my_players_frame, columns, 20)
        self.eligible_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create a button frame for my players
        my_buttons_frame = ttk.Frame(my_players_frame, style='Panel.TFrame')
        my_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(my_buttons_frame, text="Place Selected on Waivers", 
                  command=self.place_on_waivers).pack(side='left', padx=5)
        
        # Waiver wire tab
        wire_columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                       'ovr': ('OVR', 50), 'games': ('NHL Games', 80), 
                       'salary': ('Salary', 100), 'team': ('Current Team', 150),
                       'actions': ('Actions', 150)}
        
        self.waiver_tree = parent._create_treeview(waiver_wire_frame, wire_columns, 20)
        self.waiver_tree.pack(fill='both', expand=True, padx=5, pady=5)
        add_player_context_menu(self.waiver_tree, self)
        
        # Create a button frame for waiver wire
        wire_buttons_frame = ttk.Frame(waiver_wire_frame, style='Panel.TFrame')
        wire_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(wire_buttons_frame, text="Claim Selected Player", 
                  command=self.claim_from_waivers).pack(side='left', padx=5)
                  
        self.populate_eligible_players()
        self.populate_waiver_wire()
        
    def is_waiver_eligible(self, player):
        """Determine if player is waiver-eligible based on age and NHL games played."""
        # Players over 25 or with more than 160 NHL games require waivers
        nhl_games = getattr(player, 'nhl_games_played', 0)
        return player.age >= 25 or nhl_games >= 160
        
    def populate_eligible_players(self):
        """Populate the tree with waiver-eligible players from user's team."""
        self.eligible_tree.delete(*self.eligible_tree.get_children())
        
        # Get all NHL roster players who would be eligible for waivers
        eligible_players = [p for p in self.parent.user_team.roster if self.is_waiver_eligible(p)]
        
        for player in eligible_players:
            player_values = (
                player.full_name,
                player.age,
                player.primary_position.name,
                player.overall_rating(),
                getattr(player, 'nhl_games_played', 0),
                f"${player.contract.salary:,}",
                "Place on Waivers"
            )
            item = self.eligible_tree.insert('', 'end', values=player_values)
            self.eligible_tree.item(item, tags=(str(player.id),))
            
        # Configure row click event
        self.eligible_tree.bind('<ButtonRelease-1>', self.on_eligible_click)
        
    def populate_waiver_wire(self):
        """Populate the tree with players currently on the waiver wire."""
        self.waiver_tree.delete(*self.waiver_tree.get_children())
        
        for player in self.parent.waiver_list:
            player_values = (
                player.full_name,
                player.age,
                player.primary_position.name,
                player.overall_rating(),
                getattr(player, 'nhl_games_played', 0),
                f"${player.contract.salary:,}",
                player.team_name,
                "Claim"
            )
            item = self.waiver_tree.insert('', 'end', values=player_values)
            self.waiver_tree.item(item, tags=(str(player.id),))
            
        # Configure row click event
        self.waiver_tree.bind('<ButtonRelease-1>', self.on_waiver_click)
        
    def on_eligible_click(self, event):
        """Handle click on eligible players tree."""
        region = self.eligible_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.eligible_tree.identify_row(event.y)
            column = self.eligible_tree.identify_column(event.x)
            
            # If clicking on the Actions column (column #7)
            if column == '#7':
                self.place_on_waivers(item)
                
    def on_waiver_click(self, event):
        """Handle click on waiver wire tree."""
        region = self.waiver_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.waiver_tree.identify_row(event.y)
            column = self.waiver_tree.identify_column(event.x)
            
            # If clicking on the Actions column (column #8)
            if column == '#8':
                self.claim_from_waivers(item)
    
    def place_on_waivers(self, item=None):
        """Place the selected player on waivers."""
        if not item:
            selected = self.eligible_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to place on waivers.")
                return
            item = selected[0]
            
        player_id = int(self.eligible_tree.item(item, "tags")[0])
        player = next((p for p in self.parent.user_team.roster if p.id == player_id), None)
        
        if player:
            confirm = messagebox.askyesno("Confirm Waiver", 
                                         f"Place {player.full_name} on waivers? Other teams will have a chance to claim them.")
            if confirm:
                # Add to waiver list
                player.on_waivers = True
                player.waiver_days = 2  # Players stay on waivers for 2 days
                self.parent.waiver_list.append(player)
                
                # Add to news log
                self.parent.add_news(f"{player.full_name} placed on waivers by {self.parent.user_team.team_name}.")
                
                # Update the views
                self.populate_eligible_players()
                self.populate_waiver_wire()
                messagebox.showinfo("Player on Waivers", 
                                   f"{player.full_name} has been placed on waivers. "
                                   "They will remain on waivers for 2 days, during which time other teams may claim them.")
    
    def claim_from_waivers(self, item=None):
        """Claim a player from the waiver wire."""
        if not item:
            selected = self.waiver_tree.selection()
            if not selected:
                messagebox.showinfo("Selection Required", "Please select a player to claim from waivers.")
                return
            item = selected[0]
            
        player_id = int(self.waiver_tree.item(item, "tags")[0])
        player = next((p for p in self.parent.waiver_list if p.id == player_id), None)
        
        if player:
            # Check if user's team has roster space
            if len(self.parent.user_team.roster) >= 23:
                messagebox.showerror("Roster Full", 
                                    "Your NHL roster is full. Please release or reassign a player before claiming from waivers.")
                return
                
            # Check salary cap compliance
            if player.contract.salary > self.parent.user_team.cap_space:
                messagebox.showerror("Cap Space Issue", 
                                    f"You don't have enough cap space to add this player's ${player.contract.salary:,} salary.")
                return
                
            confirm = messagebox.askyesno("Confirm Claim", 
                                         f"Claim {player.full_name} from waivers? They will be added to your NHL roster.")
            if confirm:
                # Remove from previous team
                old_team = next((t for t in self.parent.league.teams if t.team_name == player.team_name), None)
                if old_team:
                    old_team.remove_player(player)
                
                # Remove from waiver list
                self.parent.waiver_list.remove(player)
                player.on_waivers = False
                player.waiver_days = 0
                
                # Add to user team
                self.parent.user_team.add_player(player)
                
                # Add to news log
                self.parent.add_news(f"{player.full_name} claimed off waivers by {self.parent.user_team.team_name}.")
                
                # Update views
                self.populate_waiver_wire()
                messagebox.showinfo("Player Claimed", 
                                   f"{player.full_name} has been claimed from waivers and added to your NHL roster.")
                
                # Refresh the main roster view if it's open
                if 'roster' in self.parent.open_windows and self.parent.open_windows['roster'].winfo_exists():
                    self.parent.open_windows['roster'].populate_trees()

class ContractExtensionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Contract Extensions")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create top panel with instructions
        instruction_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        instruction_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(instruction_frame, text="Contract Extensions", font=(parent.FONT_FAMILY, 16, 'bold'), 
                 style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        ttk.Label(instruction_frame, text="Negotiate extensions with players entering the final year of their contract. "
                                         "Per NHL rules, you can extend contracts at any time in the final year.", 
                 wraplength=900, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create notebook with tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Create tabs
        expiring_frame = ttk.Frame(notebook, style='Tab.TFrame')
        all_contracts_frame = ttk.Frame(notebook, style='Tab.TFrame')
        
        notebook.add(expiring_frame, text="Expiring Contracts")
        notebook.add(all_contracts_frame, text="All Contracts")
        
        # Expiring contracts tab
        columns = {'name': ('Player', 200), 'age': ('Age', 40), 'pos': ('Pos', 50), 
                  'ovr': ('OVR', 50), 'pot': ('POT', 50), 'salary': ('Current Salary', 120), 
                  'market': ('Market Value', 120), 'actions': ('Actions', 150)}
        
        self.expiring_tree = parent._create_treeview(expiring_frame, columns, 20)
        self.expiring_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # All contracts tab
        self.all_contracts_tree = parent._create_treeview(all_contracts_frame, columns, 20)
        self.all_contracts_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Add footer with controls
        footer_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        footer_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(footer_frame, text="Negotiate Selected", command=self.negotiate_selected).pack(side='left', padx=5)
        ttk.Button(footer_frame, text="Auto-Negotiate All", command=self.auto_negotiate_all).pack(side='left', padx=5)
        ttk.Button(footer_frame, text="Close", command=self.destroy).pack(side='right', padx=5)
        
        self.populate_tables()
        
    def populate_tables(self):
        """Populate the contract tables with data."""
        self.expiring_tree.delete(*self.expiring_tree.get_children())
        self.all_contracts_tree.delete(*self.all_contracts_tree.get_children())
        
        team = self.parent.user_team
        
        # Tree data maps to retrieve player objects
        self.parent.tree_maps[self.expiring_tree] = {}
        self.parent.tree_maps[self.all_contracts_tree] = {}
        
        # Sort players by overall rating
        sorted_players = sorted(team.roster, key=lambda p: p.overall_rating(), reverse=True)
        
        for player in sorted_players:
            # Calculate market value based on player attributes and age
            market_value = self.calculate_market_value(player)
            
            values = (
                player.full_name,
                player.age,
                player.primary_position.value,
                player.overall_rating(),
                player.potential_grade,
                f"${player.contract.salary:,}",
                f"${market_value:,}",
                "Negotiate"
            )
            
            # Add to All Contracts tab
            item_id = self.all_contracts_tree.insert('', 'end', values=values)
            self.parent.tree_maps[self.all_contracts_tree][item_id] = player
            
            # Add to Expiring Contracts tab if contract expires this season
            if player.contract.years_remaining <= 1:
                item_id = self.expiring_tree.insert('', 'end', values=values, tags=('expiring',))
                self.parent.tree_maps[self.expiring_tree][item_id] = player
                
        # Add right-click context menu for trees
        self.expiring_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.expiring_tree))
        self.all_contracts_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.all_contracts_tree))
        
        # Add double-click binding for negotiation
        self.expiring_tree.bind("<Double-1>", lambda e: self.negotiate_from_event(e, self.expiring_tree))
        self.all_contracts_tree.bind("<Double-1>", lambda e: self.negotiate_from_event(e, self.all_contracts_tree))
        
    def calculate_market_value(self, player):
        """Calculate a player's market value based on attributes, age, position, etc."""
        # Base value determined by overall rating
        base_value = player.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= player.age <= 29:
            age_modifier = 1.2
        elif player.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if player.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif player.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if player.overall_rating() >= 85 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if player.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(player.potential_grade, 1.0)
        
        # Stats performance bonus (simplified for now)
        performance_bonus = player.stats.goals * 50000 + player.stats.assists * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def _show_context_menu(self, event, tree):
        """Show right-click context menu for the tree."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        tree.selection_set(item_id)
        player = self.parent.tree_maps.get(tree, {}).get(item_id)
        if not player:
            return
            
        menu = tk.Menu(self, tearoff=0, bg="#3C3C3C", fg="white")
        menu.add_command(label="Negotiate Extension", 
                        command=lambda: self.open_negotiation_window(player))
        menu.add_command(label="View Player Profile", 
                        command=lambda: self.parent.open_player_profile(player))
        menu.tk_popup(event.x_root, event.y_root)
    
    def negotiate_from_event(self, event, tree):
        """Handle double-click on tree item."""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
            
        player = self.parent.tree_maps.get(tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
    
    def open_negotiation_window(self, player):
        """Open the negotiation window for a specific player."""
        if player.contract.years_remaining > 1:
            messagebox.showinfo("Not Eligible", 
                               f"{player.full_name} has {player.contract.years_remaining} years left on their contract. "
                               f"Per NHL rules, players can only negotiate extensions in the final year of their contract.")
            return
            
        # Calculate recommended contract offer
        market_value = self.calculate_market_value(player)
        max_years = 8  # NHL max extension is 8 years for own players
        
        # Open Advanced Contract Negotiation Window
        self.parent.open_windows['extension_negotiation'] = ExtensionNegotiationWindow(
            self.parent, player, market_value, max_years)
        self.parent.open_windows['extension_negotiation'].focus_set()
    
    def negotiate_selected(self):
        """Negotiate with the selected player."""
        selection = self.expiring_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a player to negotiate with.")
            return
            
        item_id = selection[0]
        player = self.parent.tree_maps.get(self.expiring_tree, {}).get(item_id)
        if player:
            self.open_negotiation_window(player)
    
    def auto_negotiate_all(self):
        """Auto-negotiate with all expiring contracts."""
        team = self.parent.user_team
        expiring_players = [p for p in team.roster if p.contract.years_remaining <= 1]
        
        if not expiring_players:
            messagebox.showinfo("No Expiring Contracts", "There are no players with expiring contracts.")
            return
            
        result_messages = []
        for player in expiring_players:
            market_value = self.calculate_market_value(player)
            
            # Determine years based on age and value
            if player.age <= 25:
                years = min(8, random.randint(4, 6))  # Young players get longer deals
            elif player.age <= 30:
                years = random.randint(3, 5)  # Prime-age players
            else:
                years = random.randint(1, 3)  # Older players get shorter deals
                
            # Adjust offer based on player value
            offer_percentage = random.uniform(0.9, 1.1)  # Offer between 90-110% of market value
            salary_offer = int(market_value * offer_percentage)
            
            # Simulate negotiation
            accepted = self.simulate_negotiation(player, salary_offer, years)
            
            if accepted:
                # Update player contract
                player.contract.salary = salary_offer
                player.contract.years_remaining = years
                result_messages.append(f"{player.full_name}: Accepted {years} years at ${salary_offer:,}")
            else:
                result_messages.append(f"{player.full_name}: Rejected {years} years at ${salary_offer:,}")
        
        # Show results
        result_window = tk.Toplevel(self)
        result_window.title("Auto-Negotiation Results")
        result_window.geometry("500x400")
        result_window.configure(background=self.parent.BG_COLOR)
        
        ttk.Label(result_window, text="Contract Extension Results", 
                font=(self.parent.FONT_FAMILY, 14, 'bold')).pack(pady=10)
        
        result_text = tk.Text(result_window, width=60, height=20, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        result_text.pack(pady=10, padx=10, fill='both', expand=True)
        
        for msg in result_messages:
            result_text.insert('end', msg + '\n')
        
        ttk.Button(result_window, text="Close", command=result_window.destroy).pack(pady=10)
        
        # Refresh data
        self.populate_tables()
    
    def simulate_negotiation(self, player, salary_offer, years):
        """Simulate contract negotiation based on player expectations."""
        # Calculate minimum acceptable salary based on overall rating and age
        min_salary = player.overall_rating() * 75000
        
        # Adjust for age
        if player.age >= 30:
            min_salary *= max(0.5, 1.0 - ((player.age - 30) * 0.05))
        
        # Chance of accepting depends on how good the offer is
        acceptance_chance = 0.5  # Base chance
        
        # Adjust based on salary offered vs minimum expected
        if salary_offer >= min_salary * 1.2:
            acceptance_chance += 0.4  # Great offer
        elif salary_offer >= min_salary * 1.1:
            acceptance_chance += 0.25  # Good offer
        elif salary_offer >= min_salary:
            acceptance_chance += 0.1  # Fair offer
        else:
            acceptance_chance -= 0.3  # Poor offer
        
        # Adjust based on years
        ideal_years = 8 if player.age <= 25 else 5 if player.age <= 30 else 2
        years_diff = abs(years - ideal_years)
        
        if years_diff == 0:
            acceptance_chance += 0.2  # Perfect term
        elif years_diff <= 1:
            acceptance_chance += 0.1  # Close to ideal term
        elif years_diff >= 3:
            acceptance_chance -= 0.2  # Far from ideal term
        
        # Adjust for player loyalty
        if hasattr(player, 'teamwork') and player.teamwork > 15:
            acceptance_chance += 0.1  # Loyal player
        
        # Final result
        return random.random() < max(0.05, min(0.95, acceptance_chance))

class ExtensionNegotiationWindow(tk.Toplevel):
    def __init__(self, parent, player, market_value, max_years):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.market_value = market_value
        self.max_years = max_years
        
        self.title(f"Negotiate Extension with {player.full_name}")
        self.geometry("700x600")
        self.configure(background=parent.BG_COLOR)
        
        # Main frame
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Player info section
        info_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        info_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(info_frame, text=f"{player.full_name} - {player.primary_position.value}", 
                 font=(parent.FONT_FAMILY, 16, 'bold'), style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Create two columns for player info
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(fill='x', padx=10, pady=5)
        
        # Left column
        left_col = ttk.Frame(details_frame)
        left_col.pack(side='left', fill='x', expand=True)
        
        ttk.Label(left_col, text=f"Age: {player.age}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Overall Rating: {player.overall_rating()}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(left_col, text=f"Potential: {player.potential_grade}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Right column
        right_col = ttk.Frame(details_frame)
        right_col.pack(side='right', fill='x', expand=True)
        
        ttk.Label(right_col, text=f"Current Salary: ${player.contract.salary:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Years Remaining: {player.contract.years_remaining}", style='Info.TLabel').pack(anchor='w', pady=2)
        ttk.Label(right_col, text=f"Estimated Market Value: ${market_value:,}", style='Info.TLabel').pack(anchor='w', pady=2)
        
        # Stats summary
        stats_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(stats_frame, text="Season Statistics", font=(parent.FONT_FAMILY, 12, 'bold'), 
                 style='Header.TLabel').pack(anchor='w', padx=10, pady=5)
        
        stats_text = f"Goals: {player.stats.goals}   Assists: {player.stats.assists}   Points: {player.stats.points}"
        ttk.Label(stats_frame, text=stats_text, style='Info.TLabel').pack(anchor='w', padx=10, pady=5)
        
        # Contract negotiation section
        contract_frame = ttk.LabelFrame(main_frame, text="Contract Offer", )
        contract_frame.pack(fill='x', padx=5, pady=10)
        
        # Salary slider and entry
        salary_frame = ttk.Frame(contract_frame)
        salary_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(salary_frame, text="Salary per year:", style='Info.TLabel').pack(side='left')
        
        self.salary_var = tk.StringVar(master=self, value=f"{market_value:,}")
        salary_entry = ttk.Entry(salary_frame, textvariable=self.salary_var, width=15)
        salary_entry.pack(side='left', padx=10)
        
        # Min/recommended/max salary buttons
        salary_presets = ttk.Frame(contract_frame)
        salary_presets.pack(fill='x', padx=10, pady=5)
        
        min_salary = max(750000, int(market_value * 0.8))
        recommended_salary = market_value
        max_salary = int(market_value * 1.2)
        
        ttk.Button(salary_presets, text=f"Min (${min_salary:,})", 
                  command=lambda: self.salary_var.set(f"{min_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Recommended (${recommended_salary:,})", 
                  command=lambda: self.salary_var.set(f"{recommended_salary:,}")).pack(side='left', padx=5)
        ttk.Button(salary_presets, text=f"Max (${max_salary:,})", 
                  command=lambda: self.salary_var.set(f"{max_salary:,}")).pack(side='left', padx=5)
        
        # Contract length
        years_frame = ttk.Frame(contract_frame)
        years_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(years_frame, text="Contract Length (years):", style='Info.TLabel').pack(side='left')
        
        self.years_var = tk.IntVar(master=self, value=min(5, max_years))
        years_scale = ttk.Scale(years_frame, from_=1, to=max_years, variable=self.years_var, 
                               orient='horizontal', length=200)
        years_scale.pack(side='left', padx=10)
        
        years_label = ttk.Label(years_frame, textvariable=self.years_var, style='Info.TLabel')
        years_label.pack(side='left')
        
        # No-trade clause
        ntc_frame = ttk.Frame(contract_frame)
        ntc_frame.pack(fill='x', padx=10, pady=10)
        
        self.ntc_var = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(ntc_frame, text="Include No-Trade Clause", variable=self.ntc_var,
                       style='TCheckbutton').pack(side='left')
        
        # Signing bonus
        bonus_frame = ttk.Frame(contract_frame)
        bonus_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(bonus_frame, text="Signing Bonus ($):", style='Info.TLabel').pack(side='left')
        
        self.bonus_var = tk.StringVar(master=self, value="0")
        bonus_entry = ttk.Entry(bonus_frame, textvariable=self.bonus_var, width=15)
        bonus_entry.pack(side='left', padx=10)
        
        # Total contract value display
        self.total_value_var = tk.StringVar(master=self)
        total_frame = ttk.Frame(contract_frame)
        total_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(total_frame, text="Total Contract Value:", style='Info.TLabel', font=(parent.FONT_FAMILY, 12, 'bold')).pack(side='left')
        ttk.Label(total_frame, textvariable=self.total_value_var, style='Info.TLabel', font=(parent.FONT_FAMILY, 12, 'bold')).pack(side='left', padx=10)
        
        # Update total when values change
        self.years_var.trace_add('write', self.update_total)
        self.salary_var.trace_add('write', self.update_total)
        self.bonus_var.trace_add('write', self.update_total)
        
        # Initial update
        self.update_total()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(button_frame, text="Submit Offer", command=self.submit_offer).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side='right', padx=5)
    
    def update_total(self, *args):
        """Update the total contract value display."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0
            
            total = (salary * years) + bonus
            self.total_value_var.set(f"${total:,}")
        except ValueError:
            self.total_value_var.set("Invalid input")
    
    def submit_offer(self):
        """Submit contract offer to the player."""
        try:
            # Parse salary with commas
            salary_str = self.salary_var.get().replace(',', '')
            salary = int(salary_str)
            years = self.years_var.get()
            
            # Parse bonus
            bonus_str = self.bonus_var.get().replace(',', '')
            bonus = int(bonus_str) if bonus_str else 0
            
            # Validate inputs
            if salary < 750000:
                messagebox.showerror("Invalid Salary", "Salary must be at least $750,000 (NHL minimum).")
                return
                
            if years < 1 or years > self.max_years:
                messagebox.showerror("Invalid Contract Length", 
                                   f"Contract length must be between 1 and {self.max_years} years.")
                return
                
            if bonus < 0:
                messagebox.showerror("Invalid Bonus", "Signing bonus cannot be negative.")
                return
            
            # Calculate likelihood of acceptance
            acceptance_chance = self.calculate_acceptance_chance(salary, years, bonus)
            
            # Simulate player decision
            accepted = random.random() < acceptance_chance
            
            if accepted:
                # Update player contract
                self.player.contract.salary = salary
                self.player.contract.years_remaining = years
                self.player.contract.signing_bonus = bonus
                self.player.contract.no_trade_clause = self.ntc_var.get()
                
                messagebox.showinfo("Offer Accepted", 
                                  f"{self.player.full_name} has accepted your contract extension offer.\n\n"
                                  f"{years} years at ${salary:,}/year\n"
                                  f"{'With' if self.ntc_var.get() else 'Without'} No-Trade Clause\n"
                                  f"Signing Bonus: ${bonus:,}")
                self.destroy()
            else:
                counter_years = min(years + random.randint(-1, 1), self.max_years)
                counter_salary = int(salary * random.uniform(1.05, 1.2))
                
                response = messagebox.askyesno("Offer Rejected", 
                                             f"{self.player.full_name} has rejected your contract extension offer.\n\n"
                                             f"Counter offer: {counter_years} years at ${counter_salary:,}/year\n\n"
                                             f"Would you like to accept this counter offer?")
                
                if response:
                    # Update player contract with counter offer
                    self.player.contract.salary = counter_salary
                    self.player.contract.years_remaining = counter_years
                    self.player.contract.signing_bonus = bonus
                    self.player.contract.no_trade_clause = self.ntc_var.get()
                    
                    messagebox.showinfo("Counter Offer Accepted", 
                                      f"You have accepted {self.player.full_name}'s counter offer.\n\n"
                                      f"{counter_years} years at ${counter_salary:,}/year")
                    self.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for salary, years, and bonus.")
    
    def calculate_acceptance_chance(self, salary, years, bonus):
        """Calculate the likelihood of the player accepting the contract offer."""
        # Base acceptance chance
        chance = 0.5
        
        # Adjust based on salary vs market value
        salary_ratio = salary / self.market_value
        
        if salary_ratio >= 1.1:
            chance += 0.3  # Great offer
        elif salary_ratio >= 1.0:
            chance += 0.15  # Good offer
        elif salary_ratio >= 0.9:
            chance += 0.05  # Fair offer
        else:
            chance -= 0.3  # Poor offer
        
        # Adjust based on player age and contract length
        ideal_years = 8 if self.player.age <= 25 else 5 if self.player.age <= 30 else 2
        years_diff = abs(years - ideal_years)
        
        if years_diff == 0:
            chance += 0.15  # Perfect term
        elif years_diff <= 1:
            chance += 0.05  # Close to ideal term
        elif years_diff >= 4:
            chance -= 0.15  # Far from ideal term
        
        # Bonus adds slight bonus to acceptance
        if bonus > 0:
            chance += min(0.1, bonus / (salary * years) * 0.5)
        
        # No-trade clause adds value for veterans
        if self.ntc_var.get() and self.player.age >= 28:
            chance += 0.1
        
        # Cap the chance between 5% and 95%
        return max(0.05, min(0.95, chance))

class SetCaptainsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Set Captains")
        self.geometry("400x300")
        self.configure(background='#1E1E1E')

        self.captain_var = tk.StringVar(master=self)
        self.alternate1_var = tk.StringVar(master=self)
        self.alternate2_var = tk.StringVar(master=self)

        self._create_widgets()
        self.load_captains()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)

        players = [p.full_name for p in self.parent.user_team.roster]

        ttk.Label(main_frame, text="Captain (C):").pack(pady=(0, 5))
        captain_combo = ttk.Combobox(main_frame, textvariable=self.captain_var, values=players, state='readonly')
        captain_combo.pack(fill='x', pady=(0, 10))

        ttk.Label(main_frame, text="Alternate Captain (A):").pack(pady=(0, 5))
        alt1_combo = ttk.Combobox(main_frame, textvariable=self.alternate1_var, values=players, state='readonly')
        alt1_combo.pack(fill='x', pady=(0, 10))
        
        ttk.Label(main_frame, text="Alternate Captain (A):").pack(pady=(0, 5))
        alt2_combo = ttk.Combobox(main_frame, textvariable=self.alternate2_var, values=players, state='readonly')
        alt2_combo.pack(fill='x', pady=(0, 10))

        ttk.Button(main_frame, text="Save Captains", command=self.save_captains).pack(pady=20)

    def load_captains(self):
        for p in self.parent.user_team.roster:
            if p.captaincy == 'C':
                self.captain_var.set(p.full_name)
            elif p.captaincy == 'A':
                if not self.alternate1_var.get():
                    self.alternate1_var.set(p.full_name)
                else:
                    self.alternate2_var.set(p.full_name)

    def save_captains(self):
        for p in self.parent.user_team.roster:
            p.captaincy = None

        captain_name = self.captain_var.get()
        alt1_name = self.alternate1_var.get()
        alt2_name = self.alternate2_var.get()

        for p in self.parent.user_team.roster:
            if p.full_name == captain_name:
                p.captaincy = 'C'
            elif p.full_name == alt1_name or p.full_name == alt2_name:
                p.captaincy = 'A'
        
        messagebox.showinfo("Captains Updated", "Team captaincy has been updated.")
        self.parent.update_all_views()
        self.destroy()

# --- Drag-and-Drop Edit Lines Window ---
class EditLinesWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("🏒 Elite Line Editor - Hockey Manager Pro")
        self.geometry("1400x1000")  # Increased height from 900 to 1000
        self.configure(background=parent.BG_COLOR)
        self.resizable(True, True)

        # Enhanced styling and colors
        self.ICE_COLOR = '#f8f9fa'
        self.LINE_COLOR = '#2c3e50'
        self.PLAYER_COLORS = {
            'forward': '#3498db',
            'defense': '#e67e22', 
            'goalie': '#e74c3c',
            'selected': '#f39c12',
            'highlight': '#9b59b6'
        }
        
        # Player quality colors for visual feedback
        self.QUALITY_COLORS = {
            'elite': '#27ae60',      # Green for 85+ overall
            'good': '#f39c12',       # Orange for 75-84
            'average': '#95a5a6',    # Gray for 65-74
            'poor': '#e74c3c'        # Red for <65
        }

        # Initialize tracking variables
        self.selected_player = None
        self.drag_source = None
        self.auto_save_enabled = True
        self.changes_made = False
        
        # Enhanced tooltips system
        self.tooltip_labels = {}
        self.active_tooltip = None
        
        # Stage 2: Advanced interaction tracking
        self.drag_mode = False
        self.hover_player = None
        self.line_chemistry_cache = {}
        self.undo_stack = []
        self.redo_stack = []
        self.line_suggestions = {}
        
        # Stage 2: Real-time analytics
        self.analytics_enabled = True
        self.performance_metrics = {}
        self.chemistry_warnings = []
        self.optimization_suggestions = []
        
        # Stage 3: Advanced drag-and-drop and visual features
        self.drag_data = {'active': False, 'source': None, 'target': None, 'player': None}
        self.drop_zones = {}
        self.player_widgets = {}
        self.visual_effects = {'animations': True, 'highlights': True, 'tooltips': True}
        self.player_cards = {}
        self.line_visual_feedback = {}
        self.chemistry_indicators = {}
        
        # Stage 3: Enhanced player interaction
        self.player_selection_mode = 'single'  # 'single', 'multi', 'swap'
        self.selected_players = []
        self.comparison_mode = False
        self.filter_settings = {'position': 'all', 'rating': 'all', 'availability': 'all'}
        self.sorting_criteria = 'overall'
        
        # Stage 3: Advanced visual elements
        self.hover_effects = True
        self.chemistry_visualization = True
        self.performance_indicators = True
        self.position_highlights = True
        
        # Stage 4: Complete drag-and-drop and AI features
        self.drag_preview_widget = None
        self.drop_highlight_zones = {}
        self.ai_suggestions_engine = True
        self.advanced_chemistry_model = True
        self.performance_prediction = True
        self.contextual_tooltips = {}
        
        # Stage 4: Advanced AI and optimization
        self.line_optimization_algorithms = {
            'chemistry': True,
            'balance': True,
            'matchup': True,
            'fatigue': True
        }
        self.predictive_analytics = True
        self.scenario_simulation = True
        
        # Stage 4: Enhanced visual feedback
        self.animated_transitions = True
        self.chemistry_heatmap = True
        self.performance_graphs = True
        self.interactive_ice_surface = True
        
        # Initialize essential variables for compatibility
        self.fw_vars = [[tk.StringVar(master=self) for _ in range(3)] for _ in range(4)]  # 4 lines x 3 positions
        self.df_vars = [[tk.StringVar(master=self) for _ in range(2)] for _ in range(4)]  # 4 pairs x 2 positions
        self.g_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 goalies
        self.pp1_fw_vars = [tk.StringVar(master=self) for _ in range(3)]  # 3 forwards
        self.pp1_df_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 defense
        self.pp2_fw_vars = [tk.StringVar(master=self) for _ in range(3)]  # 3 forwards
        self.pp2_df_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 defense
        self.pk1_fw_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 forwards
        self.pk1_df_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 defense
        self.pk2_fw_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 forwards
        self.pk2_df_vars = [tk.StringVar(master=self) for _ in range(2)]  # 2 defense
        self.strat_vars = [tk.StringVar(master=self) for _ in range(5)]  # 5 strategy options
        
        # Get current lineup or create new one with enhanced structure
        self.lineup = getattr(self.parent.user_team, "lineup", {
            'Forwards': [[None]*3 for _ in range(4)],
            'Defense': [[None]*2 for _ in range(4)],
            'Goalies': [None, None],
            'PP1': {'Forwards': [None, None, None], 'Defense': [None, None]},
            'PP2': {'Forwards': [None, None, None], 'Defense': [None, None]},
            'PK1': {'Forwards': [None, None], 'Defense': [None, None]},
            'PK2': {'Forwards': [None, None], 'Defense': [None, None]},
            'Strategies': {
                'EvenStrength': 'Balanced',
                'PowerPlay': 'Offensive',
                'PenaltyKill': 'Defensive',
                'LeadingBy2+': 'Defensive',
                'TrailingBy2+': 'Very Offensive',
                'ForeCheckIntensity': 50,
                'DefensiveStructure': 'Standard',
                'Aggression': 50
            },
            'LineNicknames': {
                'Forward1': 'Top Line',
                'Forward2': '2nd Line', 
                'Forward3': '3rd Line',
                'Forward4': '4th Line',
                'Defense1': 'Top Pair',
                'Defense2': '2nd Pair',
                'Defense3': '3rd Pair',
                'Defense4': '4th Pair'
            },
            'LastModified': None,
            'ChemistryBonus': {}
        })
        
        # Ensure all required keys exist with enhanced structure
        self._initialize_lineup_structure()
        
        # Get roster and create enhanced player data
        self.roster = self.parent.user_team.roster
        self.player_stats = self._calculate_enhanced_player_stats()
        
        # Create enhanced player icons
        self.player_icons = self._create_enhanced_player_icons()

        # Create modern tabbed interface
        self._create_enhanced_interface()
        
        # Initialize with current data
        self._load_current_lineup()
        
        # Bind events for enhanced interaction
        self._bind_enhanced_events()
        self.pk1_fw_vars = [tk.StringVar(master=self) for _ in range(2)]
        self.pk1_df_vars = [tk.StringVar(master=self) for _ in range(2)]
        self.pk2_fw_vars = [tk.StringVar(master=self) for _ in range(2)]
        self.pk2_df_vars = [tk.StringVar(master=self) for _ in range(2)]
        
        # Strategy variables
        self.strategy_vars = {
            'EvenStrength': tk.StringVar(master=self, value=self.lineup['Strategies'].get('EvenStrength', 'Balanced')),
            'PowerPlay': tk.StringVar(master=self, value=self.lineup['Strategies'].get('PowerPlay', 'Offensive')),
            'PenaltyKill': tk.StringVar(master=self, value=self.lineup['Strategies'].get('PenaltyKill', 'Defensive')),
            'LeadingBy2+': tk.StringVar(master=self, value=self.lineup['Strategies'].get('LeadingBy2+', 'Defensive')),
            'TrailingBy2+': tk.StringVar(master=self, value=self.lineup['Strategies'].get('TrailingBy2+', 'Very Offensive')),
            'ForeCheckIntensity': tk.IntVar(master=self, value=self.lineup['Strategies'].get('ForeCheckIntensity', 50)),
            'DefensiveStructure': tk.StringVar(master=self, value=self.lineup['Strategies'].get('DefensiveStructure', 'Standard')),
            'Aggression': tk.IntVar(master=self, value=self.lineup['Strategies'].get('Aggression', 50))
        }

        # Build the interface - COMMENTED OUT: Using enhanced tab system instead
        # self._build_even_strength_editor()
        # self._build_power_play_editor()
        # self._build_penalty_kill_editor()
        # self._build_goalie_editor()
        # self._build_strategy_editor()

    def _initialize_lineup_structure(self):
        """Initialize enhanced lineup structure with all required components"""
        required_keys = {
            'Strategies': {
                'EvenStrength': 'Balanced',
                'PowerPlay': 'Offensive', 
                'PenaltyKill': 'Defensive',
                'LeadingBy2+': 'Defensive',
                'TrailingBy2+': 'Very Offensive',
                'ForeCheckIntensity': 50,
                'DefensiveStructure': 'Standard',
                'Aggression': 50
            },
            'LineNicknames': {
                'Forward1': 'Top Line',
                'Forward2': '2nd Line',
                'Forward3': '3rd Line', 
                'Forward4': '4th Line',
                'Defense1': 'Top Pair',
                'Defense2': '2nd Pair',
                'Defense3': '3rd Pair',
                'Defense4': '4th Pair'
            },
            'ChemistryBonus': {},
            'LastModified': None
        }
        
        for key, default_value in required_keys.items():
            if key not in self.lineup:
                self.lineup[key] = default_value
        
        # Initialize basic lineup structure
        if 'Forwards' not in self.lineup:
            self.lineup['Forwards'] = [[None]*3 for _ in range(4)]
        if 'Defense' not in self.lineup:
            self.lineup['Defense'] = [[None]*2 for _ in range(4)]
        elif len(self.lineup['Defense']) < 4:
            # Migrate existing lineups to support 4 defense pairs
            while len(self.lineup['Defense']) < 4:
                self.lineup['Defense'].append([None, None])
        if 'Goalies' not in self.lineup:
            self.lineup['Goalies'] = [None, None]
        
        # Initialize special teams
        special_teams = ['PP1', 'PP2', 'PK1', 'PK2']
        for team in special_teams:
            if team not in self.lineup:
                if team.startswith('PP'):
                    self.lineup[team] = {'Forwards': [None, None, None], 'Defense': [None, None]}
                else:  # PK
                    self.lineup[team] = {'Forwards': [None, None], 'Defense': [None, None]}

    def _calculate_enhanced_player_stats(self):
        """Calculate enhanced statistics for each player for lineup optimization"""
        player_stats = {}
        
        for player in self.roster:
            # Calculate composite ratings for different situations
            overall = player.overall_rating()
            
            # Position-specific composite ratings
            if player.primary_position.value in ['LW', 'C', 'RW']:
                offensive = (getattr(player, 'shooting', 10) + getattr(player, 'passing', 10) + 
                           getattr(player, 'vision', 10)) / 3
                defensive = (getattr(player, 'checking', 10) + getattr(player, 'discipline', 10)) / 2
                speed = getattr(player, 'skating', 10)
                
                player_stats[player.id] = {
                    'overall': overall,
                    'offensive': offensive,
                    'defensive': defensive, 
                    'speed': speed,
                    'pp_rating': (offensive + speed) / 2,
                    'pk_rating': (defensive + speed) / 2,
                    'chemistry_factors': self._get_chemistry_factors(player),
                    'quality_tier': self._get_quality_tier(overall),
                    'injury_risk': getattr(player, 'injury_proneness', 10)
                }
            elif player.primary_position.value in ['LD', 'RD', 'D']:
                defensive = (getattr(player, 'checking', 10) + getattr(player, 'positioning', 10)) / 2
                offensive = (getattr(player, 'passing', 10) + getattr(player, 'shooting', 10)) / 2
                speed = getattr(player, 'skating', 10)
                
                player_stats[player.id] = {
                    'overall': overall,
                    'defensive': defensive,
                    'offensive': offensive,
                    'speed': speed,
                    'pp_rating': (offensive + speed) / 2,
                    'pk_rating': (defensive + speed) / 2,
                    'chemistry_factors': self._get_chemistry_factors(player),
                    'quality_tier': self._get_quality_tier(overall),
                    'injury_risk': getattr(player, 'injury_proneness', 10)
                }
            else:  # Goalie
                saves = getattr(player, 'goaltending', 10)
                reflexes = getattr(player, 'reflexes', 10)
                positioning = getattr(player, 'positioning', 10)
                
                player_stats[player.id] = {
                    'overall': overall,
                    'saves': saves,
                    'reflexes': reflexes,
                    'positioning': positioning,
                    'quality_tier': self._get_quality_tier(overall),
                    'injury_risk': getattr(player, 'injury_proneness', 10)
                }
        
        return player_stats

    def _get_chemistry_factors(self, player):
        """Get factors that influence player chemistry"""
        return {
            'nationality': getattr(player, 'nationality', 'Unknown'),
            'age_group': 'veteran' if player.age > 30 else 'prime' if player.age > 25 else 'young',
            'style': self._determine_play_style(player),
            'handedness': getattr(player, 'handedness', 'Right')
        }

    def _determine_play_style(self, player):
        """Determine player's playing style based on attributes"""
        if hasattr(player, 'checking') and player.checking > 15:
            return 'physical'
        elif hasattr(player, 'speed') and player.speed > 15:
            return 'speed'
        elif hasattr(player, 'vision') and player.vision > 15:
            return 'playmaker'
        else:
            return 'balanced'

    def _get_quality_tier(self, overall):
        """Determine player quality tier for visual feedback"""
        if overall >= 85:
            return 'elite'
        elif overall >= 75:
            return 'good'
        elif overall >= 65:
            return 'average'
        else:
            return 'poor'

    def get_eligible_players_for_position(self, position):
        """Get players eligible for a specific position"""
        from game_classes import PlayerPosition
        eligible = []
        
        for player in self.roster:
            # Check if player can play this position
            if position == 'G' and player.primary_position == PlayerPosition.GOALIE:
                eligible.append(player)
            elif position in ['LW', 'C', 'RW'] and player.primary_position in [
                PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING
            ]:
                eligible.append(player)
            elif position in ['LD', 'RD', 'D'] and player.primary_position in [
                PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE
            ]:
                eligible.append(player)
        
        return eligible

    def get_eligible_defensemen_for_position(self, position):
        """Get defensemen eligible for a specific position"""
        from game_classes import PlayerPosition
        eligible = []
        
        for player in self.roster:
            # Only include defensemen
            if player.primary_position in [
                PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE
            ]:
                eligible.append(player)
        
        return eligible

    def get_eligible_pk_forwards(self):
        """Get forwards eligible for penalty kill"""
        from game_classes import PlayerPosition
        eligible = []
        
        for player in self.roster:
            # Only include forwards
            if player.primary_position in [
                PlayerPosition.LEFT_WING, PlayerPosition.CENTER, PlayerPosition.RIGHT_WING
            ]:
                eligible.append(player)
        
        return eligible

    def _create_player_icon(self, color, size=30):
        """Create a circular player icon"""
        icon = tk.PhotoImage(width=size, height=size)
        radius = size // 2
        # Draw a circle
        for y in range(size):
            for x in range(size):
                # Calculate if point is in circle
                dx = x - radius
                dy = y - radius
                if dx*dx + dy*dy <= radius*radius:
                    icon.put(color, (x, y))
        return icon
        
    def _create_ice_surface(self, canvas, width, height):
        """Create a visual representation of an ice hockey rink"""
        # Rink outline
        canvas.create_rectangle(10, 10, width-10, height-10, outline='#0099cc', width=2)
        
        # Center line
        canvas.create_line(width//2, 10, width//2, height-10, fill='red', width=2)
        canvas.create_oval(width//2-30, height//2-30, width//2+30, height//2+30, outline='blue', width=2)
        
        # Blue lines
        canvas.create_line(width//3, 10, width//3, height-10, fill='blue', width=2)
        canvas.create_line(2*width//3, 10, 2*width//3, height-10, fill='blue', width=2)
        
        # Goal creases
        canvas.create_arc(30, height//2-50, 130, height//2+50, start=270, extent=180, outline='red', width=2)
        canvas.create_arc(width-130, height//2-50, width-30, height//2+50, start=90, extent=180, outline='red', width=2)
        
        # Faceoff circles
        for x_pos in [width//4, 3*width//4]:
            for y_offset in [-height//4, height//4]:
                y_pos = height//2 + y_offset
                canvas.create_oval(x_pos-30, y_pos-30, x_pos+30, y_pos+30, outline='red', width=1)
                
    def _position_to_coordinates(self, position, side, width, height):
        """Convert player position to coordinates on the ice surface"""
        # Maps player positions to x,y coordinates for visualization
        x_offset = 0 if side == 'left' else width
        x_multiplier = 1 if side == 'left' else -1
        
        position_map = {
            # Left side positions (attacking left to right)
            'LW1': (width * 0.35, height * 0.3),
            'C1': (width * 0.35, height * 0.5),
            'RW1': (width * 0.35, height * 0.7),
            'LW2': (width * 0.25, height * 0.3),
            'C2': (width * 0.25, height * 0.5),
            'RW2': (width * 0.25, height * 0.7),
            'LW3': (width * 0.15, height * 0.3),
            'C3': (width * 0.15, height * 0.5),
            'RW3': (width * 0.15, height * 0.7),
            'LW4': (width * 0.05, height * 0.3),
            'C4': (width * 0.05, height * 0.5),
            'RW4': (width * 0.05, height * 0.7),
            'LD1': (width * 0.15, height * 0.35),
            'RD1': (width * 0.15, height * 0.65),
            'LD2': (width * 0.10, height * 0.35),
            'RD2': (width * 0.10, height * 0.65),
            'LD3': (width * 0.05, height * 0.35),
            'RD3': (width * 0.05, height * 0.65),
            'G1': (width * 0.05, height * 0.5),
            'G2': (width * 0.03, height * 0.4),
            
            # Power play positions
            'PP_LW': (width * 0.4, height * 0.25),
            'PP_C': (width * 0.4, height * 0.5),
            'PP_RW': (width * 0.4, height * 0.75),
            'PP_LD': (width * 0.2, height * 0.35),
            'PP_RD': (width * 0.2, height * 0.65),
            
            # Penalty kill positions
            'PK_LW': (width * 0.3, height * 0.4),
            'PK_RW': (width * 0.3, height * 0.6),
            'PK_LD': (width * 0.15, height * 0.35),
            'PK_RD': (width * 0.15, height * 0.65),
        }
        
        x, y = position_map.get(position, (width * 0.5, height * 0.5))
        
        # Adjust for which side of ice
        if side == 'right':
            x = width - x
            
        return (x, y)
    
    def _build_even_strength_editor(self):
        """Build the even strength lines editor - streamlined for easy editing"""
        # Create a scrollable canvas
        canvas = tk.Canvas(self.even_frame, bg=self.parent.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.even_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Add mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Create the main content frame inside the scrollable frame
        main_frame = ttk.Frame(scrollable_frame, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Forward lines section
        fw_frame = ttk.LabelFrame(main_frame, text="📈 Forward Lines", style='Panel.TLabelframe')
        fw_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        # Build forward lines
        positions = ["LW", "C", "RW"]
        for i in range(4):  # 4 lines
            line_frame = ttk.Frame(fw_frame, style='Panel.TFrame')
            line_frame.pack(fill="x", padx=10, pady=8)
            
            # Line header with rating and tools
            line_header = ttk.Frame(line_frame, style='Panel.TFrame')
            line_header.pack(fill="x", pady=(0, 5))
            
            line_label = ttk.Label(line_header, text=f"Line {i+1}", style='Title.TLabel', 
                                 font=(self.parent.FONT_FAMILY, 12, 'bold'))
            line_label.pack(side="left", padx=5)
            
            # Line rating display
            line_rating_label = ttk.Label(line_header, text="Rating: --", style='TLabel')
            line_rating_label.pack(side="left", padx=10)
            
            # Quick optimize button for this line
            ttk.Button(line_header, text="Auto-Set", 
                      command=lambda idx=i: self._optimize_single_line(idx, 'Forwards'),
                      style='TButton').pack(side="right", padx=5)
            
            # Calculate and display line chemistry when fully populated
            chem_det = self.calculate_line_chemistry_detailed(self.lineup['Forwards'][i])
            if chem_det:
                _score, chemistry, _factors = chem_det
                chem_label = ttk.Label(line_header, text=f"Chemistry: {_score} ({chemistry})",
                                     foreground=self._get_chemistry_color(chemistry),
                                     font=('Segoe UI', 9, 'bold'))
                chem_label.pack(side="right", padx=5)
            
            # Position selector frame
            pos_frame = ttk.Frame(line_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", pady=2)
            
            for j, pos in enumerate(positions):
                # Create position frame with dropdown and player info
                pos_selection = ttk.Frame(pos_frame, style='Panel.TFrame')
                pos_selection.pack(side="left", fill="x", expand=True, padx=5)
                
                # Position label
                ttk.Label(pos_selection, text=pos).pack(anchor="w")
                
                # Get list of eligible players for this position
                eligible_players = self.get_eligible_players_for_position(pos)
                player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
                
                # Create dropdown
                cb = ttk.Combobox(pos_selection, textvariable=self.fw_vars[i][j], 
                                values=player_names, state="readonly", width=30)
                cb.pack(fill="x", pady=2)
                
                # Bind selection to update the visualization
                cb.bind("<<ComboboxSelected>>", lambda e, line=i: self._update_analytics_display())
                
                # Set current value if player is assigned
                if self.lineup['Forwards'][i][j]:
                    player = self.lineup['Forwards'][i][j]
                    self.fw_vars[i][j].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    
                    # Show player stats
                    stats = f"OVR: {player.overall_rating()} | " + \
                          f"{pos} Rating: {self.calculate_position_rating(player, pos)}"
                    ttk.Label(pos_selection, text=stats, font=(self.parent.FONT_FAMILY, 9)).pack(anchor="w")
        
        # Defense pairs section
        df_frame = ttk.LabelFrame(main_frame, text="🛡️ Defense Pairs", style='Panel.TLabelframe')
        df_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        positions = ["LD", "RD"]
        for i in range(4):  # 4 pairs
            pair_frame = ttk.Frame(df_frame, style='Panel.TFrame')
            pair_frame.pack(fill="x", padx=10, pady=3)  # Reduced padding from 8 to 3
            
            # Compact pair header with rating and tools in one line
            pair_header = ttk.Frame(pair_frame, style='Panel.TFrame')
            pair_header.pack(fill="x", pady=(0, 2))  # Reduced padding from 5 to 2
            
            pair_label = ttk.Label(pair_header, text=f"Pair {i+1}", style='Title.TLabel', 
                                 font=(self.parent.FONT_FAMILY, 10, 'bold'))  # Reduced font size from 12 to 10
            pair_label.pack(side="left", padx=3)  # Reduced padding from 5 to 3
            
            # Quick optimize button for this pair
            ttk.Button(pair_header, text="Auto", 
                      command=lambda idx=i: self._optimize_single_line(idx, 'Defense'),
                      style='TButton', width=3).pack(side="right", padx=2)  # Compact button
            
            # Calculate and display pair chemistry when fully populated
            chem_det = self.calculate_defense_chemistry_detailed(self.lineup['Defense'][i])
            if chem_det:
                _score, chemistry, _factors = chem_det
                chem_label = ttk.Label(pair_header, text=f"Chem: {_score} ({chemistry})",
                                     foreground=self._get_chemistry_color(chemistry),
                                     font=(self.parent.FONT_FAMILY, 9, 'bold'))  # Smaller font
                chem_label.pack(side="right", padx=5)
            
            # Compact position selector frame - horizontal layout
            pos_frame = ttk.Frame(pair_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", pady=2)  # Reduced padding from 5 to 2
            
            for j, pos in enumerate(positions):
                # Create compact position frame with dropdown
                pos_selection = ttk.Frame(pos_frame, style='Panel.TFrame')
                pos_selection.pack(side="left", fill="x", expand=True, padx=4)  # Reduced padding from 8 to 4
                
                # Compact position label
                pos_label = ttk.Label(pos_selection, text=f"{pos}:", style='TLabel',
                                    font=(self.parent.FONT_FAMILY, 9, 'bold'))  # Smaller, simpler label
                pos_label.pack(anchor="w", pady=(0, 1))  # Reduced padding from 3 to 1
                
                eligible_players = self.get_eligible_defensemen_for_position(pos)
                player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
                
                cb = ttk.Combobox(pos_selection, textvariable=self.df_vars[i][j],
                                values=player_names, state="readonly", width=25)  # Reduced width from 30 to 25
                cb.pack(fill="x", pady=1)  # Reduced padding from 2 to 1
                
                # Bind selection to update analytics
                cb.bind("<<ComboboxSelected>>", lambda e, pair=i: self._update_analytics_display())
                
                if self.lineup['Defense'][i][j]:
                    player = self.lineup['Defense'][i][j]
                    self.df_vars[i][j].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    
                    # Show compact player stats on same line as dropdown (optional - remove if too cramped)
                    # stats = f"OVR: {player.overall_rating()}"
                    # ttk.Label(pos_selection, text=stats, font=(self.parent.FONT_FAMILY, 8)).pack(anchor="w")

    def _build_power_play_editor(self):
        """Build the power play editor - streamlined and efficient"""
        # Create main frame
        main_frame = ttk.Frame(self.pp_frame, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # PP1 unit
        pp1_frame = ttk.LabelFrame(main_frame, text="Power Play Unit 1", style='Panel.TLabelframe')
        pp1_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        # PP1 header with optimization
        pp1_header = ttk.Frame(pp1_frame, style='Panel.TFrame')
        pp1_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ttk.Label(pp1_header, text="PP1 - Top Unit", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side="left")
        
        ttk.Button(pp1_header, text="Auto-Set PP1", 
                  command=lambda: self._optimize_power_play_unit(1),
                  style='TButton').pack(side="right", padx=5)
        
        # Forward positions for PP1
        fw_frame = ttk.LabelFrame(pp1_frame, text="🏒 Forwards", style='Panel.TLabelframe')
        fw_frame.pack(fill="x", padx=10, pady=5)
        
        pp_fw_positions = ["LW", "C", "RW"]
        for i, pos in enumerate(pp_fw_positions):
            pos_frame = ttk.Frame(fw_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=10, pady=5)
            
            # Position label with icon
            pos_label = ttk.Label(pos_frame, text=f"📍 {pos}:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 10, 'bold'))
            pos_label.pack(side="left", padx=(5, 10))
            
            eligible_players = self.get_eligible_players_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pp1_fw_vars[i], 
                            values=player_names, state="readonly", width=35)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
            
            # Set current value if player is assigned
            if self.lineup['PP1']['Forwards'][i]:
                player = self.lineup['PP1']['Forwards'][i]
                self.pp1_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # Defense positions for PP1
        df_frame = ttk.LabelFrame(pp1_frame, text="🛡️ Defense", style='Panel.TLabelframe')
        df_frame.pack(fill="x", padx=10, pady=5)
        
        pp_df_positions = ["LD", "RD"]
        for i, pos in enumerate(pp_df_positions):
            pos_frame = ttk.Frame(df_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=10, pady=5)
            
            # Position label with icon
            pos_label = ttk.Label(pos_frame, text=f"📍 {pos}:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 10, 'bold'))
            pos_label.pack(side="left", padx=(5, 10))
            
            eligible_players = self.get_eligible_defensemen_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pp1_df_vars[i], 
                            values=player_names, state="readonly", width=35)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
            
            # Set current value if player is assigned
            if self.lineup['PP1']['Defense'][i]:
                player = self.lineup['PP1']['Defense'][i]
                self.pp1_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # PP2 unit
        pp2_frame = ttk.LabelFrame(main_frame, text="Power Play Unit 2", style='Panel.TLabelframe')
        pp2_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        # PP2 header with optimization
        pp2_header = ttk.Frame(pp2_frame, style='Panel.TFrame')
        pp2_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ttk.Label(pp2_header, text="PP2 - Second Unit", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side="left")
        
        ttk.Button(pp2_header, text="Auto-Set PP2", 
                  command=lambda: self._optimize_power_play_unit(2),
                  style='TButton').pack(side="right", padx=5)
        
        # Forward positions for PP2
        fw_frame = ttk.LabelFrame(pp2_frame, text="🏒 Forwards", style='Panel.TLabelframe')
        fw_frame.pack(fill="x", padx=10, pady=5)
        
        for i, pos in enumerate(pp_fw_positions):
            pos_frame = ttk.Frame(fw_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=10, pady=5)
            
            # Position label with icon
            pos_label = ttk.Label(pos_frame, text=f"📍 {pos}:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 10, 'bold'))
            pos_label.pack(side="left", padx=(5, 10))
            
            eligible_players = self.get_eligible_players_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pp2_fw_vars[i], 
                            values=player_names, state="readonly", width=35)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
            
            # Set current value if player is assigned
            if self.lineup['PP2']['Forwards'][i]:
                player = self.lineup['PP2']['Forwards'][i]
                self.pp2_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # Defense positions for PP2
        df_frame = ttk.LabelFrame(pp2_frame, text="🛡️ Defense", style='Panel.TLabelframe')
        df_frame.pack(fill="x", padx=10, pady=5)
        
        for i, pos in enumerate(pp_df_positions):
            pos_frame = ttk.Frame(df_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=5, pady=2)
            
            ttk.Label(pos_frame, text=f"{pos}:").pack(side="left", padx=5)
            
            eligible_players = self.get_eligible_defensemen_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pp2_df_vars[i], 
                            values=player_names, state="readonly", width=30)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw_power_play_on_ice())
            
            # Set current value if player is assigned
            if self.lineup['PP2']['Defense'][i]:
                player = self.lineup['PP2']['Defense'][i]
                self.pp2_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
    
    def _build_penalty_kill_editor(self):
        """Build the penalty kill editor - streamlined and efficient"""
        # Create main frame
        main_frame = ttk.Frame(self.pk_frame, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # PK1 unit
        pk1_frame = ttk.LabelFrame(main_frame, text="🛡️ Penalty Kill Unit 1", style='Panel.TLabelframe')
        pk1_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        # PK1 header with optimization
        pk1_header = ttk.Frame(pk1_frame, style='Panel.TFrame')
        pk1_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ttk.Label(pk1_header, text="PK1 - Top Defensive Unit", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side="left")
        
        ttk.Button(pk1_header, text="Auto-Set PK1", 
                  command=lambda: self._optimize_penalty_kill_unit(1),
                  style='TButton').pack(side="right", padx=5)
        
        # Forward positions for PK1
        fw_frame = ttk.LabelFrame(pk1_frame, text="🏒 Forwards (2)", style='Panel.TLabelframe')
        fw_frame.pack(fill="x", padx=10, pady=5)
        
        pk_fw_positions = ["LW", "RW"]
        for i, pos in enumerate(pk_fw_positions):
            pos_frame = ttk.Frame(fw_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=10, pady=5)
            
            # Position label with icon
            pos_label = ttk.Label(pos_frame, text=f"📍 {pos}:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 10, 'bold'))
            pos_label.pack(side="left", padx=(5, 10))
            
            # For PK, prioritize defensive and high-stamina forwards
            eligible_players = self.get_eligible_pk_forwards()
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pk1_fw_vars[i], 
                            values=player_names, state="readonly", width=35)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
            
            # Set current value if player is assigned
            if self.lineup['PK1']['Forwards'][i]:
                player = self.lineup['PK1']['Forwards'][i]
                self.pk1_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # Defense positions for PK1
        df_frame = ttk.LabelFrame(pk1_frame, text="🛡️ Defense (2)", style='Panel.TLabelframe')
        df_frame.pack(fill="x", padx=10, pady=5)
        
        pk_df_positions = ["LD", "RD"]
        for i, pos in enumerate(pk_df_positions):
            pos_frame = ttk.Frame(df_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=10, pady=5)
            
            # Position label with icon
            pos_label = ttk.Label(pos_frame, text=f"📍 {pos}:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 10, 'bold'))
            pos_label.pack(side="left", padx=(5, 10))
            
            eligible_players = self.get_eligible_defensemen_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pk1_df_vars[i], 
                            values=player_names, state="readonly", width=35)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
            
            # Set current value if player is assigned
            if self.lineup['PK1']['Defense'][i]:
                player = self.lineup['PK1']['Defense'][i]
                self.pk1_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # PK2 unit
        pk2_frame = ttk.LabelFrame(main_frame, text="🛡️ Penalty Kill Unit 2", style='Panel.TLabelframe')
        pk2_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        # PK2 header with optimization
        pk2_header = ttk.Frame(pk2_frame, style='Panel.TFrame')
        pk2_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ttk.Label(pk2_header, text="PK2 - Second Defensive Unit", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 12, 'bold')).pack(side="left")
        
        ttk.Button(pk2_header, text="Auto-Set PK2", 
                  command=lambda: self._optimize_penalty_kill_unit(2),
                  style='TButton').pack(side="right", padx=5)
        
        # Forward positions for PK2
        fw_frame = ttk.LabelFrame(pk2_frame, text="Forwards", style='Panel.TFrame')
        fw_frame.pack(fill="x", padx=5, pady=5)
        
        for i, pos in enumerate(pk_fw_positions):
            pos_frame = ttk.Frame(fw_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=5, pady=2)
            
            ttk.Label(pos_frame, text=f"{pos}:").pack(side="left", padx=5)
            
            eligible_players = self.get_eligible_pk_forwards()
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pk2_fw_vars[i], 
                            values=player_names, state="readonly", width=30)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw_penalty_kill_on_ice())
            
            # Set current value if player is assigned
            if self.lineup['PK2']['Forwards'][i]:
                player = self.lineup['PK2']['Forwards'][i]
                self.pk2_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
        
        # Defense positions for PK2
        df_frame = ttk.LabelFrame(pk2_frame, text="Defense", style='Panel.TFrame')
        df_frame.pack(fill="x", padx=5, pady=5)
        
        for i, pos in enumerate(pk_df_positions):
            pos_frame = ttk.Frame(df_frame, style='Panel.TFrame')
            pos_frame.pack(fill="x", padx=5, pady=2)
            
            ttk.Label(pos_frame, text=f"{pos}:").pack(side="left", padx=5)
            
            eligible_players = self.get_eligible_defensemen_for_position(pos)
            player_names = [""] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in eligible_players]
            
            cb = ttk.Combobox(pos_frame, textvariable=self.pk2_df_vars[i], 
                            values=player_names, state="readonly", width=30)
            cb.pack(side="left", fill="x", expand=True, padx=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw_penalty_kill_on_ice())
            
            # Set current value if player is assigned
            if self.lineup['PK2']['Defense'][i]:
                player = self.lineup['PK2']['Defense'][i]
                self.pk2_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")

    def calculate_position_rating(self, player, position):
        """Calculate a player's rating at a specific position"""
        if not player:
            return 0
            
        # Position-specific attribute weightings
        position_weights = {
            "LW": {
                'skating': 0.15, 
                'shooting': 0.20, 
                'passing': 0.15, 
                'offensive_awareness': 0.15,
                'shooting_accuracy': 0.10,
                'shooting_power': 0.10,
                'deking': 0.05,
                'defensive_awareness': 0.05,
                'acceleration': 0.05
            },
            "C": {
                'skating': 0.15, 
                'passing': 0.20, 
                'offensive_awareness': 0.15,
                'faceoffs': 0.15,
                'vision': 0.10,
                'defensive_awareness': 0.10,
                'shooting': 0.05,
                'work_rate': 0.05,
                'hockey_iq': 0.05
            },
            "RW": {
                'skating': 0.15, 
                'shooting': 0.20, 
                'passing': 0.15, 
                'offensive_awareness': 0.15,
                'shooting_accuracy': 0.10,
                'shooting_power': 0.10,
                'deking': 0.05,
                'defensive_awareness': 0.05,
                'acceleration': 0.05
            },
            "LD": {
                'defensive_awareness': 0.20,
                'checking': 0.15,
                'skating': 0.10,
                'strength': 0.10,
                'shot_blocking': 0.10,
                'passing': 0.10,
                'shooting': 0.05,
                'puck_protection': 0.10,
                'work_rate': 0.10
            },
            "RD": {
                'defensive_awareness': 0.20,
                'checking': 0.15,
                'skating': 0.10,
                'strength': 0.10,
                'shot_blocking': 0.10,
                'passing': 0.10,
                'shooting': 0.05,
                'puck_protection': 0.10,
                'work_rate': 0.10
            }
        }
        
        # If player is out of position, apply penalty
        primary_pos = player.primary_position.name
        out_of_position_penalty = 1.0  # No penalty for natural position
        
        if position != primary_pos:
            # Center can play wing with small penalty
            if primary_pos == "C" and position in ["LW", "RW"]:
                out_of_position_penalty = 0.9
            # Wingers can play opposite wing with moderate penalty
            elif primary_pos in ["LW", "RW"] and position in ["LW", "RW"]:
                out_of_position_penalty = 0.85
            # Defensemen can play either side with small penalty
            elif primary_pos in ["LD", "RD", "D"] and position in ["LD", "RD"]:
                out_of_position_penalty = 0.95
            # Forwards playing defense or vice versa is a major penalty
            else:
                out_of_position_penalty = 0.7
        
        # Get the weights for this position
        weights = position_weights.get(position, {})
        if not weights:
            return player.overall_rating() * out_of_position_penalty
        
        # Calculate weighted average of attributes
        total_weight = 0
        weighted_sum = 0
        
        for attr, weight in weights.items():
            attr_value = getattr(player, attr, 0)
            weighted_sum += attr_value * weight
            total_weight += weight
        
        # Handle division by zero
        if total_weight == 0:
            return player.overall_rating() * out_of_position_penalty
            
        position_rating = (weighted_sum / total_weight) * out_of_position_penalty
        return int(position_rating)
    
    def calculate_line_chemistry(self, line):
        """Calculate chemistry rating for a forward line (uses detailed model)."""
        det = self.calculate_line_chemistry_detailed(line)
        return det[1] if det else None

    def get_line_chemistry_score(self, line):
        """Chemistry score 0-100 for a forward line, or None if incomplete."""
        det = self.calculate_line_chemistry_detailed(line)
        return det[0] if det else None
    
    def calculate_defense_chemistry(self, pair):
        """Calculate chemistry rating for a defense pair (uses detailed model)."""
        det = self.calculate_defense_chemistry_detailed(pair)
        return det[1] if det else None

    def get_defense_chemistry_score(self, pair):
        """Chemistry score 0-100 for a defense pair, or None if incomplete."""
        det = self.calculate_defense_chemistry_detailed(pair)
        return det[0] if det else None
    
    def _get_chemistry_color(self, chemistry):
        """Get color for chemistry rating"""
        if chemistry == "Excellent":
            return "#27ae60"  # Green
        elif chemistry == "Good":
            return "#2980b9"  # Blue
        elif chemistry == "Average":
            return "#f39c12"  # Orange
        else:
            return "#c0392b"  # Red

    # ------------------------------------------------------------------
    # Detailed chemistry model: score (0-100) + per-factor +/- breakdown.
    # Each factor is a tuple: (delta, title, detail). Positive deltas help,
    # negative deltas hurt. This powers the Chemistry tab and the per-line
    # labels, so players can SEE why a line clicks or not.
    # ------------------------------------------------------------------
    @staticmethod
    def _chemistry_rating(score):
        if score >= 80:
            return "Excellent"
        if score >= 65:
            return "Good"
        if score >= 45:
            return "Average"
        return "Poor"

    @staticmethod
    def _teamwork_factor(players, n):
        # Teamwork runs ~20-69 league-wide, median ~48: score relative to that.
        avg = sum(p.teamwork for p in players) / n
        delta = max(-18, min(18, round((avg - 48) * 2)))
        if delta >= 9:
            return (delta, "High teamwork", f"Avg teamwork {avg:.0f} - well above league average, they read off each other")
        if delta >= 0:
            return (delta, "Decent teamwork", f"Avg teamwork {avg:.0f} - around league average")
        return (delta, "Low teamwork", f"Avg teamwork {avg:.0f} - below league average, too many individuals")

    def calculate_line_chemistry_detailed(self, line):
        """Forward line chemistry -> (score, rating, factors). None if incomplete."""
        if not all(line):
            return None
        factors = []
        score = 50

        # Non-forwards at forward slots: hard penalty
        for i, pos_name in enumerate(["LW", "C", "RW"]):
            p = line[i]
            pname = p.primary_position.value
            if pname not in ["LW", "C", "RW"]:
                d = -25
                factors.append((d, f"{p.full_name} out of position",
                                f"A {pname} slotted at {pos_name} - big drag on the line"))
                score += d

        # Teamwork
        d, t, det = self._teamwork_factor(line, 3)
        factors.append((d, t, det))
        score += d

        # Playstyle fit (shoot vs pass tendencies)
        tends = [p.shoot_pass_tendency for p in line]
        var = max(tends) - min(tends)
        if var <= 20:
            d, t, det = 12, "Playstyles mesh", f"Shoot/pass tendencies within {var:.0f} - everyone on the same page"
        elif var <= 30:
            d, t, det = 6, "Compatible styles", f"Tendencies within {var:.0f} - mostly complementary"
        elif var <= 40:
            d, t, det = 0, "Mixed tendencies", f"Tendencies spread {var:.0f} - no clear identity"
        else:
            d, t, det = -12, "Clashing tendencies", f"Tendencies spread {var:.0f} - snipers and passers pulling apart"
        factors.append((d, t, det))
        score += d

        # Center fit
        center = line[1]
        cname = center.primary_position.value
        if cname == "C":
            d, t, det = 8, "Natural center", f"{center.full_name} is a true center - draws the line together"
        elif cname in ["LW", "RW"]:
            d, t, det = -8, "Winger forced at center", f"{center.full_name} is a winger - faceoffs and coverage suffer"
        else:
            d, t, det = 0, "", ""
        if d:
            factors.append((d, t, det))
            score += d

        # Winger fit
        off_wing = []
        for i, pos_name in ((0, "LW"), (2, "RW")):
            p = line[i]
            if p.primary_position.value not in ["LW", "C", "RW"]:
                continue  # already penalized above
            if p.primary_position.value not in ["LW", "RW"]:
                off_wing.append((p, pos_name))
        if off_wing:
            for p, pos_name in off_wing:
                d = -10
                factors.append((d, f"{p.full_name} off-wing",
                                f"A center playing {pos_name} - workable, but not ideal"))
                score += d
        else:
            d = 4
            factors.append((d, "Natural wingers", "Both wingers on their proper side"))
            score += d

        # Shooter + playmaker balance
        has_shooter = any(p.shoot_pass_tendency >= 65 for p in line)
        has_playmaker = any(p.shoot_pass_tendency <= 35 for p in line)
        if has_shooter and has_playmaker:
            d = 6
            factors.append((d, "Shooter + playmaker", "A finisher and a distributor on the same unit"))
            score += d

        score = max(5, min(99, score))
        factors.sort(key=lambda f: f[0])
        return (score, self._chemistry_rating(score), factors)

    def calculate_defense_chemistry_detailed(self, pair):
        """Defense pair chemistry -> (score, rating, factors). None if incomplete."""
        if not all(pair):
            return None
        factors = []
        score = 50

        for i, pos_name in enumerate(["LD", "RD"]):
            p = pair[i]
            pname = p.primary_position.value
            if pname not in ["LD", "RD", "D"]:
                d = -25
                factors.append((d, f"{p.full_name} out of position",
                                f"A {pname} on the blue line - major liability"))
                score += d

        # Teamwork
        d, t, det = self._teamwork_factor(pair, 2)
        factors.append((d, t, det))
        score += d

        # Style complement: offensive D vs defensive D
        def tilt(p):
            diff = p.offensive_awareness - p.defensive_awareness
            if diff > 3:
                return "offensive"
            if diff < -3:
                return "defensive"
            return "balanced"
        tilts = [tilt(p) for p in pair]
        if "offensive" in tilts and "defensive" in tilts:
            d, t, det = 12, "Perfect complement", "One jumps into the play, one holds the fort"
        elif tilts[0] == tilts[1] and tilts[0] != "balanced":
            d, t, det = -8, "Redundant styles", f"Two {tilts[0]} defensemen - same strengths, same holes"
        else:
            d, t, det = 4, "Steady pairing", "No glaring style conflict"
        factors.append((d, t, det))
        score += d

        # Sides
        sides_ok = (pair[0].primary_position.value in ["LD", "D"] and
                    pair[1].primary_position.value in ["RD", "D"])
        if sides_ok:
            d = 8
            factors.append((d, "Proper sides", "LD on the left, RD on the right - clean breakouts"))
            score += d
        else:
            for i, pos_name in enumerate(["LD", "RD"]):
                p = pair[i]
                pname = p.primary_position.value
                if pname in ["LD", "RD", "D"] and pname not in (["LD", "D"] if i == 0 else ["RD", "D"]):
                    d = -8
                    factors.append((d, f"{p.full_name} on off-side",
                                    f"A {pname} playing {pos_name} - retrievals and first passes suffer"))
                    score += d

        score = max(5, min(99, score))
        factors.sort(key=lambda f: f[0])
        return (score, self._chemistry_rating(score), factors)
    
    # def draw_current_lines_on_ice(self):
    #     """Draw current lines on ice visualization - DISABLED"""
    #     pass
        # """Draw the current lines on the ice surface"""
        # self.ice_canvas.delete("player")
        # 
        # width = self.ice_canvas.winfo_width()
        # height = self.ice_canvas.winfo_height()
        # 
        # # Get currently selected line (from the tab)
        # current_line = self.notebook.index(self.notebook.select())
        # if current_line == 0:  # Even strength tab
        #     # Draw forward line 1 and defense pair 1
        #     # Forwards
        #     for i, pos in enumerate(["LW", "C", "RW"]):
        #         name = self.fw_vars[0][i].get().split(' (')[0] if self.fw_vars[0][i].get() else ""
        #         player = next((p for p in self.roster if p.full_name == name), None)
        #         
        #         if player:
        #             pos_key = f"{pos}1"
        #             x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #             
        #             # Create player icon
        #             self.ice_canvas.create_image(x, y, image=self.player_img, tags="player")
        #             self.ice_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")
        #             
        #     # Defense
        #     for i, pos in enumerate(["LD", "RD"]):
        #         name = self.df_vars[0][i].get().split(' (')[0] if self.df_vars[0][i].get() else ""
        #         player = next((p for p in self.roster if p.full_name == name), None)
        #         
        #         if player:
        #             pos_key = f"{pos}1"
        #             x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #             
        #             # Create player icon
        #             self.ice_canvas.create_image(x, y, image=self.player_img, tags="player")
        #             self.ice_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")
        #     
        #     # Add a goalie
        #     name = self.g_vars[0].get().split(' (')[0] if self.g_vars[0].get() else ""
        #     goalie = next((p for p in self.roster if p.full_name == name), None)
        #     
        #     if goalie:
        #         x, y = self._position_to_coordinates("G1", 'left', width, height)
        #         self.ice_canvas.create_image(x, y, image=self.goalie_img, tags="player")
        #         self.ice_canvas.create_text(x, y+20, text=f"{goalie.last_name}", tags="player")
    
    # def draw_power_play_on_ice(self):
    #     """Draw the power play units on ice visualization - DISABLED"""
    #     pass
        # """Draw the power play units on the ice surface"""
        # self.pp_canvas.delete("player")
        # 
        # width = self.pp_canvas.winfo_width()
        # height = self.pp_canvas.winfo_height()
        # 
        # # Draw the first power play unit
        # # PP1 Forwards
        # for i, pos_key in enumerate(["PP_LW", "PP_C", "PP_RW"]):
        #     name = self.pp1_fw_vars[i].get().split(' (')[0] if self.pp1_fw_vars[i].get() else ""
        #     player = next((p for p in self.roster if p.full_name == name), None)
        #     
        #     if player:
        #         x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #         
        #         # Create player icon
        #         self.pp_canvas.create_image(x, y, image=self.player_img, tags="player")
        #         self.pp_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")
        # 
        # # PP1 Defense
        # for i, pos_key in enumerate(["PP_LD", "PP_RD"]):
        #     name = self.pp1_df_vars[i].get().split(' (')[0] if self.pp1_df_vars[i].get() else ""
        #     player = next((p for p in self.roster if p.full_name == name), None)
        #     
        #     if player:
        #         x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #         
        #         # Create player icon
        #         self.pp_canvas.create_image(x, y, image=self.player_img, tags="player")
        #         self.pp_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")
    
    # def draw_penalty_kill_on_ice(self):
    #     """Draw the penalty kill units on ice visualization - DISABLED"""
    #     pass
        # """Draw the penalty kill units on the ice surface"""
        # self.pk_canvas.delete("player")
        # 
        # width = self.pk_canvas.winfo_width()
        # height = self.pk_canvas.winfo_height()
        # 
        # # Draw the first penalty kill unit
        # # PK1 Forwards
        # for i, pos_key in enumerate(["PK_LW", "PK_RW"]):
        #     name = self.pk1_fw_vars[i].get().split(' (')[0] if self.pk1_fw_vars[i].get() else ""
        #     player = next((p for p in self.roster if p.full_name == name), None)
        #     
        #     if player:
        #         x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #         
        #         # Create player icon
        #         self.pk_canvas.create_image(x, y, image=self.player_img, tags="player")
        #         self.pk_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")
        # 
        # # PK1 Defense
        # for i, pos_key in enumerate(["PK_LD", "PK_RD"]):
        #     name = self.pk1_df_vars[i].get().split(' (')[0] if self.pk1_df_vars[i].get() else ""
        #     player = next((p for p in self.roster if p.full_name == name), None)
        #     
        #     if player:
        #         x, y = self._position_to_coordinates(pos_key, 'left', width, height)
        #         
        #         # Create player icon
        #         self.pk_canvas.create_image(x, y, image=self.player_img, tags="player")
        #         self.pk_canvas.create_text(x, y+20, text=f"{player.last_name}", tags="player")

    def save_lines(self):
        """Save all line configurations and strategies"""
        # Update forwards
        for i in range(4):
            for j in range(3):
                name = self.fw_vars[i][j].get().split(' (')[0] if self.fw_vars[i][j].get() else ""
                self.lineup['Forwards'][i][j] = next(
                    (p for p in self.roster if p.full_name == name), None)

        # Update defense
        for i in range(3):
            for j in range(2):
                name = self.df_vars[i][j].get().split(' (')[0] if self.df_vars[i][j].get() else ""
                self.lineup['Defense'][i][j] = next(
                    (p for p in self.roster if p.full_name == name), None)

        # Update goalies
        for i in range(2):
            name = self.g_vars[i].get().split(' (')[0] if self.g_vars[i].get() else ""
            self.lineup['Goalies'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
                
        # Update power play units
        for i in range(3):  # 3 forwards
            name = self.pp1_fw_vars[i].get().split(' (')[0] if self.pp1_fw_vars[i].get() else ""
            self.lineup['PP1']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pp2_fw_vars[i].get().split(' (')[0] if self.pp2_fw_vars[i].get() else ""
            self.lineup['PP2']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
        
        for i in range(2):  # 2 defensemen
            name = self.pp1_df_vars[i].get().split(' (')[0] if self.pp1_df_vars[i].get() else ""
            self.lineup['PP1']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pp2_df_vars[i].get().split(' (')[0] if self.pp2_df_vars[i].get() else ""
            self.lineup['PP2']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
        
        # Update penalty kill units
        for i in range(2):  # 2 forwards
            name = self.pk1_fw_vars[i].get().split(' (')[0] if self.pk1_fw_vars[i].get() else ""
            self.lineup['PK1']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pk2_fw_vars[i].get().split(' (')[0] if self.pk2_fw_vars[i].get() else ""
            self.lineup['PK2']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
        
        for i in range(2):  # 2 defensemen
            name = self.pk1_df_vars[i].get().split(' (')[0] if self.pk1_df_vars[i].get() else ""
            self.lineup['PK1']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pk2_df_vars[i].get().split(' (')[0] if self.pk2_df_vars[i].get() else ""
            self.lineup['PK2']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
        
        # Update strategies (if they exist)
        if hasattr(self, 'strat_vars'):
            strategy_keys = ['EvenStrength', 'PowerPlay', 'PenaltyKill', 'LeadingBy2+', 'TrailingBy2+']
            for i, var in enumerate(self.strat_vars):
                if i < len(strategy_keys) and var.get():
                    self.lineup['Strategies'][strategy_keys[i]] = var.get()

        # Save the lineup to the team
        self.parent.user_team.lineup = self.lineup
        self.parent.update_all_views()
        messagebox.showinfo("Success", "Lines have been saved!")
        self.destroy()

    def set_best_lines(self):
        """Auto-generate the best possible lines"""
        from main import best_lines
        self.parent.user_team.lineup = best_lines(self.parent.user_team)
        self.destroy()
        EditLinesWindow(self.parent)

    def reset_lines(self):
        """Reset all line changes and re-open the window"""
        self.destroy()
        EditLinesWindow(self.parent)
        
    def check_chemistry(self):
        """Check chemistry for all lines and display a report"""
        chemistry_report = "Team Line Chemistry Report\n\n"
        
        # Check forward lines
        chemistry_report += "Forward Lines:\n"
        for i in range(4):
            line = [self.lineup['Forwards'][i][j] for j in range(3)]
            chemistry = self.calculate_line_chemistry(line)
            chemistry_report += f"Line {i+1}: {chemistry if chemistry else 'Incomplete'}\n"
        
        # Check defense pairs
        chemistry_report += "\nDefense Pairs:\n"
        for i in range(4):
            pair = [self.lineup['Defense'][i][j] for j in range(2)]
            chemistry = self.calculate_defense_chemistry(pair)
            chemistry_report += f"Pair {i+1}: {chemistry if chemistry else 'Incomplete'}\n"
        
        # Check special teams
        chemistry_report += "\nPower Play Units:\n"
        pp1_forwards = self.lineup['PP1']['Forwards']
        pp1_defense = self.lineup['PP1']['Defense']
        pp2_forwards = self.lineup['PP2']['Forwards']
        pp2_defense = self.lineup['PP2']['Defense']
        
        chemistry_report += f"PP1: {all(pp1_forwards) and all(pp1_defense)}\n"
        chemistry_report += f"PP2: {all(pp2_forwards) and all(pp2_defense)}\n"
        
        chemistry_report += "\nPenalty Kill Units:\n"
        pk1_forwards = self.lineup['PK1']['Forwards']
        pk1_defense = self.lineup['PK1']['Defense']
        pk2_forwards = self.lineup['PK2']['Forwards']
        pk2_defense = self.lineup['PK2']['Defense']
        
        chemistry_report += f"PK1: {all(pk1_forwards) and all(pk1_defense)}\n"
        chemistry_report += f"PK2: {all(pk2_forwards) and all(pk2_defense)}\n"
        
        messagebox.showinfo("Team Chemistry Report", chemistry_report)

    def _build_goalie_editor(self):
        """Build the goalie lineup editor - streamlined and efficient"""
        main_frame = ttk.Frame(self.g_frame, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header with optimization
        header_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        header_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(header_frame, text="🥅 Goalie Depth Chart", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 14, 'bold')).pack(side="left")
        
        ttk.Button(header_frame, text="Auto-Set Best", 
                  command=self._optimize_goalies,
                  style='TButton').pack(side="right", padx=5)
        
        # Goalies container
        goalies_frame = ttk.LabelFrame(main_frame, text="🥅 Goaltender Assignments", style='Panel.TLabelframe')
        goalies_frame.pack(fill="x", pady=5)
        
        goalies = [p for p in self.roster if p.primary_position.value == 'G']
        goalie_names = ["None"] + [f"{p.full_name} ({p.primary_position.value}) - {p.overall_rating()}" for p in goalies]
        
        # Starter goalie
        starter_frame = ttk.Frame(goalies_frame, style='Panel.TFrame')
        starter_frame.pack(fill="x", padx=10, pady=8)
        
        starter_label = ttk.Label(starter_frame, text="🌟 Starting Goalie:", style='TLabel',
                                font=(self.parent.FONT_FAMILY, 11, 'bold'))
        starter_label.pack(side="left", padx=(5, 15))
        
        starter_combo = ttk.Combobox(starter_frame, textvariable=self.g_vars[0], 
                                   values=goalie_names, width=35, state="readonly")
        starter_combo.pack(side="left", fill="x", expand=True, padx=5)
        starter_combo.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
        
        # Backup goalie
        backup_frame = ttk.Frame(goalies_frame, style='Panel.TFrame')
        backup_frame.pack(fill="x", padx=10, pady=8)
        
        backup_label = ttk.Label(backup_frame, text="🔄 Backup Goalie:", style='TLabel',
                               font=(self.parent.FONT_FAMILY, 11, 'bold'))
        backup_label.pack(side="left", padx=(5, 15))
        
        backup_combo = ttk.Combobox(backup_frame, textvariable=self.g_vars[1], 
                                  values=goalie_names, width=35, state="readonly")
        backup_combo.pack(side="left", fill="x", expand=True, padx=5)
        backup_combo.bind("<<ComboboxSelected>>", lambda e: self._update_analytics_display())
        
        # Goalie stats display
        stats_frame = ttk.LabelFrame(main_frame, text="Goalie Comparison", style='Panel.TLabelframe')
        stats_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        self.goalie_stats_text = tk.Text(stats_frame, height=8, wrap=tk.WORD,
                                       background=self.parent.CONTENT_BG,
                                       foreground=self.parent.TEXT_COLOR,
                                       font=(self.parent.FONT_FAMILY, 9))
        stats_scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.goalie_stats_text.yview)
        self.goalie_stats_text.configure(yscrollcommand=stats_scrollbar.set)
        
        self.goalie_stats_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        stats_scrollbar.pack(side="right", fill="y")
        
        # Initialize stats display
        self._update_goalie_stats_display()
    
    def _optimize_goalies(self):
        """Automatically set the best goalies based on ratings"""
        goalies = [p for p in self.roster if p.primary_position.value == 'G']
        if not goalies:
            return
            
        # Sort by overall rating
        goalies.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Set starter and backup
        self.g_vars[0].set(f"{goalies[0].full_name} ({goalies[0].primary_position.value}) - {goalies[0].overall_rating()}")
        
        if len(goalies) > 1:
            self.g_vars[1].set(f"{goalies[1].full_name} ({goalies[1].primary_position.value}) - {goalies[1].overall_rating()}")
        else:
            self.g_vars[1].set("None")
        
        self._update_goalie_stats_display()
        self._update_analytics_display()
    
    def _update_goalie_stats_display(self):
        """Update the goalie comparison stats display"""
        try:
            self.goalie_stats_text.delete(1.0, tk.END)
            
            goalies = [p for p in self.roster if p.primary_position.value == 'G']
            if not goalies:
                self.goalie_stats_text.insert(tk.END, "No goalies available on roster.")
                return
            
            # Sort by rating for display
            goalies.sort(key=lambda p: p.overall_rating(), reverse=True)
            
            self.goalie_stats_text.insert(tk.END, "🥅 GOALIE DEPTH CHART ANALYSIS\n")
            self.goalie_stats_text.insert(tk.END, "=" * 50 + "\n\n")
            
            for i, goalie in enumerate(goalies, 1):
                role = "🌟 STARTER" if i == 1 else "🔄 BACKUP" if i == 2 else "🏒 RESERVE"
                self.goalie_stats_text.insert(tk.END, f"{role}: {goalie.full_name}\n")
                self.goalie_stats_text.insert(tk.END, f"   Overall: {goalie.overall_rating()}/20\n")
                self.goalie_stats_text.insert(tk.END, f"   Goaltending: {goalie.goaltending}/20\n")
                self.goalie_stats_text.insert(tk.END, f"   Reflexes: {goalie.reflexes}/20\n")
                self.goalie_stats_text.insert(tk.END, f"   Positioning: {goalie.positioning}/20\n")
                self.goalie_stats_text.insert(tk.END, f"   Rebound Control: {goalie.rebound_control}/20\n")
                self.goalie_stats_text.insert(tk.END, f"   Age: {goalie.age}\n\n")
            
            # Add recommendations
            if len(goalies) >= 2:
                starter, backup = goalies[0], goalies[1]
                self.goalie_stats_text.insert(tk.END, "💡 RECOMMENDATIONS:\n")
                self.goalie_stats_text.insert(tk.END, f"• Start {starter.full_name} for best performance\n")
                self.goalie_stats_text.insert(tk.END, f"• Use {backup.full_name} as reliable backup\n")
                
                if starter.overall_rating() - backup.overall_rating() <= 2:
                    self.goalie_stats_text.insert(tk.END, "• Consider rotating goalies - ratings are close\n")
                    
        except AttributeError:
            # If stats text widget doesn't exist yet
            pass

    def _build_strategy_editor(self):
        """Build the team tactics editor: clean sections, aligned controls."""
        main_frame = ttk.Frame(self.strat_frame, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        header_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        header_frame.pack(fill="x", pady=(0, 16))

        ttk.Label(header_frame, text="Team Tactics", style='Title.TLabel',
                 font=(self.parent.FONT_FAMILY, 16, 'bold')).pack(side="left")
        ttk.Label(header_frame, text="Your game plan shapes how the team plays in every situation.",
                 style='Muted.TLabel').pack(side="left", padx=(12, 0))

        ttk.Button(header_frame, text="Smart Setup",
                  command=self._optimize_strategies,
                  style='Secondary.TButton').pack(side="right")

        # Scrollable content
        canvas = tk.Canvas(main_frame, background=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def section_card(title):
            card = ttk.LabelFrame(scrollable_frame, text=title, style='Card.TLabelframe')
            card.pack(fill="x", pady=(0, 12), padx=2)
            return card

        card_bg = self.parent.modern_theme.colors.tertiary_bg

        def tactic_row(parent_frame, label, values, current, attr, hint):
            row = ttk.Frame(parent_frame, style='Card.TFrame')
            row.pack(fill="x", padx=14, pady=7)
            ttk.Label(row, text=label, style='TLabel', width=16, anchor="w",
                     font=(self.parent.FONT_FAMILY, 11, 'bold'),
                     background=card_bg).pack(side="left")
            combo = ttk.Combobox(row, values=values, width=18, state="readonly")
            combo.set(current)
            combo.pack(side="left", padx=(16, 0))
            combo.bind("<<ComboboxSelected>>",
                       lambda e, a=attr, c=combo: self._on_tactic_changed(a, c.get()))
            ttk.Label(row, text=hint, style='Muted.TLabel',
                     background=card_bg).pack(side="left", padx=(12, 0))
            return combo

        # Game situations
        situations = section_card("Game Situations")
        es_combo = tactic_row(
            situations, "Even Strength",
            ["Very Defensive", "Defensive", "Balanced", "Offensive", "Very Offensive"],
            getattr(self.parent.user_team, 'tactic_even_strength', 'Balanced'),
            'tactic_even_strength', "5v5 play style")
        pp_combo = tactic_row(
            situations, "Power Play",
            ["Conservative", "Balanced", "Offensive", "Very Offensive"],
            getattr(self.parent.user_team, 'tactic_power_play', 'Offensive'),
            'tactic_power_play', "Man-advantage approach")
        pk_combo = tactic_row(
            situations, "Penalty Kill",
            ["Very Defensive", "Defensive", "Balanced", "Aggressive"],
            getattr(self.parent.user_team, 'tactic_penalty_kill', 'Defensive'),
            'tactic_penalty_kill', "Short-handed defense")

        # Advanced
        tactics = section_card("Advanced")
        matching_combo = tactic_row(
            tactics, "Line Matching",
            ["Aggressive", "Standard", "Conservative"],
            getattr(self.parent.user_team, 'tactic_line_matching', 'Standard'),
            'tactic_line_matching', "How strictly lines are matched to opponents")

        # Analysis
        analysis = section_card("Strategy Analysis")
        self.strategy_analysis_text = tk.Text(analysis, height=6, wrap=tk.WORD,
                                            background=card_bg,
                                            foreground=self.parent.TEXT_COLOR,
                                            font=(self.parent.FONT_FAMILY, 10),
                                            relief="flat", padx=10, pady=8)
        analysis_scrollbar = ttk.Scrollbar(analysis, orient="vertical",
                                          command=self.strategy_analysis_text.yview)
        self.strategy_analysis_text.configure(yscrollcommand=analysis_scrollbar.set)

        self.strategy_analysis_text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        analysis_scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.strategy_combos = {
            'even_strength': es_combo,
            'power_play': pp_combo,
            'penalty_kill': pk_combo,
            'line_matching': matching_combo
        }

        self._update_strategy_analysis()
    
    def _optimize_strategies(self):
        """Automatically set optimal strategies based on team composition"""
        # Analyze team strengths
        forwards = [p for p in self.roster if p.primary_position.value in ['LW', 'C', 'RW']]
        defensemen = [p for p in self.roster if p.primary_position.value in ['LD', 'RD']]
        
        if not forwards or not defensemen:
            return
        
        # Calculate team averages
        avg_offense = sum(p.shooting + p.passing + p.vision for p in forwards) / (len(forwards) * 3)
        avg_defense = sum(p.checking + p.positioning + p.discipline for p in defensemen) / (len(defensemen) * 3)
        avg_speed = sum(p.skating for p in self.roster) / len(self.roster)
        
        # Set strategies based on team strengths
        if avg_offense > 14:
            self.strategy_combos['even_strength'].set("Offensive")
            self.strategy_combos['power_play'].set("Very Offensive")
        elif avg_offense > 12:
            self.strategy_combos['even_strength'].set("Balanced")
            self.strategy_combos['power_play'].set("Offensive")
        else:
            self.strategy_combos['even_strength'].set("Defensive")
            self.strategy_combos['power_play'].set("Balanced")
        
        if avg_defense > 14:
            self.strategy_combos['penalty_kill'].set("Aggressive")
        elif avg_defense > 12:
            self.strategy_combos['penalty_kill'].set("Defensive")
        else:
            self.strategy_combos['penalty_kill'].set("Very Defensive")
        
        if avg_speed > 14:
            self.strategy_combos['line_matching'].set("Aggressive")
        else:
            self.strategy_combos['line_matching'].set("Standard")
        
        self._update_strategy_analysis()
    
    def _on_tactic_changed(self, attr, value):
        """Persist a tactic choice to the user team, then refresh the analysis."""
        try:
            if hasattr(self, 'parent') and hasattr(self.parent, 'user_team') and self.parent.user_team:
                setattr(self.parent.user_team, attr, value)
        except Exception:
            pass
        self._update_strategy_analysis()

    def _update_strategy_analysis(self):
        """Update the strategy analysis display and save tactics to team"""
        try:
            self.strategy_analysis_text.delete(1.0, tk.END)
            
            # Get current strategies
            es_strat = self.strategy_combos['even_strength'].get()
            pp_strat = self.strategy_combos['power_play'].get()
            pk_strat = self.strategy_combos['penalty_kill'].get()
            matching_strat = self.strategy_combos['line_matching'].get()
            
            # Save tactics to the user's team (connects UI to sim engine)
            if hasattr(self, 'parent') and hasattr(self.parent, 'user_team') and self.parent.user_team:
                team = self.parent.user_team
                team.tactic_even_strength = es_strat
                team.tactic_power_play = pp_strat
                team.tactic_penalty_kill = pk_strat
                team.tactic_line_matching = matching_strat
            
            self.strategy_analysis_text.insert(tk.END, "🎯 CURRENT STRATEGY ANALYSIS\n")
            self.strategy_analysis_text.insert(tk.END, "=" * 40 + "\n\n")
            
            # Strategy impact analysis
            self.strategy_analysis_text.insert(tk.END, f"⚖️ Even Strength ({es_strat}):\n")
            if es_strat == "Very Offensive":
                self.strategy_analysis_text.insert(tk.END, "   High scoring potential, but vulnerable defensively\n")
            elif es_strat == "Offensive":
                self.strategy_analysis_text.insert(tk.END, "   Good offensive pressure with moderate defense\n")
            elif es_strat == "Balanced":
                self.strategy_analysis_text.insert(tk.END, "   Equal focus on offense and defense\n")
            elif es_strat == "Defensive":
                self.strategy_analysis_text.insert(tk.END, "   Strong defensive play, limited offense\n")
            else:
                self.strategy_analysis_text.insert(tk.END, "   Maximum defensive focus, minimal offense\n")
            
            self.strategy_analysis_text.insert(tk.END, f"\n⚡ Power Play ({pp_strat}):\n")
            if pp_strat == "Very Offensive":
                self.strategy_analysis_text.insert(tk.END, "   All-out attack, high risk/reward\n")
            elif pp_strat == "Offensive":
                self.strategy_analysis_text.insert(tk.END, "   Aggressive scoring approach\n")
            elif pp_strat == "Balanced":
                self.strategy_analysis_text.insert(tk.END, "   Controlled pressure with defensive awareness\n")
            else:
                self.strategy_analysis_text.insert(tk.END, "   Patient approach, prevent short-handed goals\n")
            
            self.strategy_analysis_text.insert(tk.END, f"\n🛡️ Penalty Kill ({pk_strat}):\n")
            if pk_strat == "Aggressive":
                self.strategy_analysis_text.insert(tk.END, "   Press the puck, create short-handed chances\n")
            elif pk_strat == "Defensive":
                self.strategy_analysis_text.insert(tk.END, "   Solid defensive structure\n")
            else:
                self.strategy_analysis_text.insert(tk.END, "   Conservative, protect the goal at all costs\n")
            
            self.strategy_analysis_text.insert(tk.END, f"\n🔄 Line Matching ({matching_strat}):\n")
            if matching_strat == "Aggressive":
                self.strategy_analysis_text.insert(tk.END, "   Quick line changes to exploit matchups\n")
            elif matching_strat == "Standard":
                self.strategy_analysis_text.insert(tk.END, "   Regular rotation with some matching\n")
            else:
                self.strategy_analysis_text.insert(tk.END, "   Simple rotation, avoid risky changes\n")
            
            # Strategy recommendations
            self.strategy_analysis_text.insert(tk.END, "\n💡 RECOMMENDATIONS:\n")
            
            # Analyze team composition for suggestions
            forwards = [p for p in self.roster if p.primary_position.value in ['LW', 'C', 'RW']]
            if forwards:
                avg_offense = sum(p.shooting + p.passing + p.vision for p in forwards) / (len(forwards) * 3)
                if avg_offense > 14 and es_strat in ["Defensive", "Very Defensive"]:
                    self.strategy_analysis_text.insert(tk.END, "• Consider more offensive play with your skilled forwards\n")
                elif avg_offense < 12 and es_strat in ["Offensive", "Very Offensive"]:
                    self.strategy_analysis_text.insert(tk.END, "• Your forwards may struggle with aggressive offense\n")
                    
        except (AttributeError, KeyError):
            # If widgets don't exist yet or combo not set
            pass

    # Enhanced methods for Stage 1 improvements (placeholder implementations)
    def _create_enhanced_interface(self):
        """Create the enhanced tabbed interface with Stage 2 improvements"""
        # Main container with advanced layout
        main_container = ttk.Frame(self, style='Panel.TFrame')
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top toolbar with advanced controls
        self._create_advanced_toolbar(main_container)
        
        # Main content area with paned window for resizable sections
        content_paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        content_paned.pack(fill="both", expand=True, pady=(10, 0))
        
        # Left panel: Line editor with drag-and-drop
        left_frame = ttk.Frame(content_paned, style='Panel.TFrame')
        content_paned.add(left_frame, weight=2)
        
        # Right panel: Analytics and suggestions
        right_frame = ttk.Frame(content_paned, style='Panel.TFrame')
        content_paned.add(right_frame, weight=1)
        
        # Create enhanced notebook for line editing
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True)
        
        # Create frames for each tab with enhanced features
        self.even_frame = self._create_enhanced_tab_frame(self.notebook, "Even Strength")
        self.pp_frame = self._create_enhanced_tab_frame(self.notebook, "Power Play") 
        self.pk_frame = self._create_enhanced_tab_frame(self.notebook, "Penalty Kill")
        self.g_frame = self._create_enhanced_tab_frame(self.notebook, "Goalies")
        self.strat_frame = self._create_enhanced_tab_frame(self.notebook, "Strategies")
        self.analytics_frame = self._create_enhanced_tab_frame(self.notebook, "📊 Analytics")
        
        # Add frames to notebook with clean labels
        self.notebook.add(self.even_frame, text="Even Strength")
        self.notebook.add(self.pp_frame, text="Power Play")
        self.notebook.add(self.pk_frame, text="Penalty Kill")
        self.notebook.add(self.g_frame, text="Goalies")
        self.notebook.add(self.strat_frame, text="Tactics")
        self.chem_frame = self._create_enhanced_tab_frame(self.notebook, "Chemistry")
        self.notebook.add(self.chem_frame, text="Chemistry")
        self.notebook.add(self.analytics_frame, text="Analytics")
        
        # Create the right panel content
        self._create_analytics_panel(right_frame)
        self._create_suggestions_panel(right_frame)
        
        # Stage 3: Add player browser panel
        self._create_player_browser_panel(right_frame)
        
        # Stage 4: Add advanced AI panel
        self._create_ai_optimization_panel(right_frame)
        
        # Build enhanced tab content with Stage 3 features
        self._build_enhanced_even_strength_tab()
        self._build_enhanced_power_play_tab()
        self._build_enhanced_penalty_kill_tab()
        self._build_enhanced_goalie_tab()
        self._build_enhanced_strategy_tab()
        self._build_chemistry_tab()
        self._build_real_time_analytics_tab()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_lines_tab_changed)
        
        # Stage 3: Initialize advanced features
        self._initialize_drag_drop_system()
        self._initialize_visual_effects()
        self._create_player_cards()
        
        # Stage 4: Initialize AI and advanced features
        self._initialize_ai_optimization_engine()
        self._initialize_predictive_analytics()
        self._initialize_interactive_features()
        
        # Enhanced button panel with more options
        self._create_enhanced_button_panel(main_container)
        
        # Stage 3: Bind advanced events
        self._bind_stage3_events()
        
        # Initialize real-time updates (disabled for stability)
        # if hasattr(self, 'analytics_enabled'):
        #     self._start_real_time_updates()

    def _create_advanced_toolbar(self, parent):
        """Create streamlined toolbar: primary actions stand out, the rest stay quiet."""
        toolbar = ttk.Frame(parent, style='Panel.TFrame')
        toolbar.pack(fill="x", pady=(0, 10))

        # Left side: history + primary actions
        left_toolbar = ttk.Frame(toolbar, style='Panel.TFrame')
        left_toolbar.pack(side="left", fill="x", expand=True)

        ttk.Button(left_toolbar, text="↶ Undo", command=self.undo_action,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(left_toolbar, text="↷ Redo", command=self.redo_action,
                  style='Secondary.TButton').pack(side="left", padx=(0, 16))

        ttk.Button(left_toolbar, text="Auto-Optimize", command=self.auto_optimize_lines,
                  style='TButton').pack(side="left", padx=(0, 6))
        ttk.Button(left_toolbar, text="AI Optimize", command=self.ai_optimize_lineup,
                  style='Secondary.TButton').pack(side="left", padx=(0, 16))

        # Secondary tools
        ttk.Button(left_toolbar, text="Shuffle", command=self.shuffle_lines,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(left_toolbar, text="Predict", command=self.show_performance_prediction,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(left_toolbar, text="Matchup", command=self.optimize_for_matchup,
                  style='Secondary.TButton').pack(side="left", padx=(0, 16))

        # Selection mode
        mode_frame = ttk.Frame(left_toolbar, style='Panel.TFrame')
        mode_frame.pack(side="left", padx=(0, 16))
        ttk.Label(mode_frame, text="Mode:", style='TLabel').pack(side="left")

        self.selection_mode_var = tk.StringVar(master=self, value=self.player_selection_mode)
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.selection_mode_var,
                                 values=['single', 'multi', 'swap'], width=8, state="readonly")
        mode_combo.pack(side="left", padx=(6, 0))
        mode_combo.bind('<<ComboboxSelected>>', self._on_selection_mode_change)

        # Import/Export (quiet)
        ttk.Button(left_toolbar, text="Import", command=self.import_lines,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(left_toolbar, text="Export", command=self.export_lines,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))

        # Right side: display toggles + status
        right_toolbar = ttk.Frame(toolbar, style='Panel.TFrame')
        right_toolbar.pack(side="right")

        self.animations_var = tk.BooleanVar(master=self, value=self.visual_effects['animations'])
        ttk.Checkbutton(right_toolbar, text="Animations", variable=self.animations_var,
                       command=self._toggle_animations).pack(side="left", padx=(0, 8))

        self.chemistry_viz_var = tk.BooleanVar(master=self, value=self.chemistry_visualization)
        ttk.Checkbutton(right_toolbar, text="Chemistry", variable=self.chemistry_viz_var,
                       command=self._toggle_chemistry_viz).pack(side="left", padx=(0, 16))

        self.auto_save_var = tk.BooleanVar(master=self, value=self.auto_save_enabled)
        auto_save_check = ttk.Checkbutton(right_toolbar, text="Auto-save",
                                         variable=self.auto_save_var,
                                         command=self.toggle_auto_save)
        auto_save_check.pack(side="left", padx=(0, 8))

        self.changes_label = ttk.Label(right_toolbar, text="", foreground="orange")
        self.changes_label.pack(side="left")

    def _create_enhanced_tab_frame(self, parent, tab_name):
        """Create enhanced tab frame with Stage 2 improvements"""
        frame = ttk.Frame(parent, style='Panel.TFrame')
        
        # Add drop zone capabilities for drag-and-drop
        frame.bind("<Button-1>", lambda e: self._on_tab_click(e, tab_name))
        frame.bind("<B1-Motion>", lambda e: self._on_tab_drag(e, tab_name))
        frame.bind("<ButtonRelease-1>", lambda e: self._on_tab_drop(e, tab_name))
        
        return frame

    def _create_analytics_panel(self, parent):
        """Create real-time analytics panel"""
        analytics_label = ttk.Label(parent, text="Real-Time Analytics",
                                   style='Heading.TLabel')
        analytics_label.pack(pady=(0, 10), anchor="w", padx=4)
        
        # Analytics scrollable frame
        analytics_canvas = tk.Canvas(parent, height=200, bg=self.parent.CONTENT_BG)
        analytics_scrollbar = ttk.Scrollbar(parent, orient="vertical", 
                                           command=analytics_canvas.yview)
        self.analytics_content = ttk.Frame(analytics_canvas, style='Panel.TFrame')
        
        analytics_canvas.configure(yscrollcommand=analytics_scrollbar.set)
        analytics_canvas.pack(side="left", fill="both", expand=True)
        analytics_scrollbar.pack(side="right", fill="y")
        
        analytics_canvas.create_window((0, 0), window=self.analytics_content, anchor="nw")
        
        # Initialize analytics display
        self._update_analytics_display()

    def _create_suggestions_panel(self, parent):
        """Create AI suggestions panel"""
        suggestions_label = ttk.Label(parent, text="Smart Suggestions",
                                     style='Heading.TLabel')
        suggestions_label.pack(pady=(16, 8), anchor="w", padx=4)
        
        # Suggestions frame
        self.suggestions_frame = ttk.Frame(parent, style='Panel.TFrame')
        self.suggestions_frame.pack(fill="both", expand=True)
        
        # Initialize suggestions
        self._update_suggestions_display()

    def _create_player_browser_panel(self, parent):
        """Create advanced player browser panel for Stage 3"""
        browser_label = ttk.Label(parent, text="Player Browser", style='Heading.TLabel')
        browser_label.pack(pady=(16, 8), anchor="w", padx=4)
        
        # Filter controls
        filter_frame = ttk.Frame(parent, style='Panel.TFrame')
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Position filter
        ttk.Label(filter_frame, text="Position:", style='TLabel').pack(anchor="w")
        self.position_filter_var = tk.StringVar(master=self, value="all")
        position_combo = ttk.Combobox(filter_frame, textvariable=self.position_filter_var,
                                     values=["all", "C", "LW", "RW", "LD", "RD", "G"], 
                                     width=10, state="readonly")
        position_combo.pack(fill="x", pady=(2, 5))
        position_combo.bind('<<ComboboxSelected>>', self._on_filter_change)
        
        # Rating filter
        ttk.Label(filter_frame, text="Rating:", style='TLabel').pack(anchor="w")
        self.rating_filter_var = tk.StringVar(master=self, value="all")
        rating_combo = ttk.Combobox(filter_frame, textvariable=self.rating_filter_var,
                                   values=["all", "85+", "80-84", "75-79", "70-74", "<70"],
                                   width=10, state="readonly")
        rating_combo.pack(fill="x", pady=(2, 5))
        rating_combo.bind('<<ComboboxSelected>>', self._on_filter_change)
        
        # Player list with enhanced features
        self.player_listbox = tk.Listbox(parent, height=12,
                                        background=self.parent.CONTENT_BG,
                                        foreground=self.parent.TEXT_COLOR,
                                        selectbackground=self.parent.ACCENT_COLOR)
        scrollbar_players = ttk.Scrollbar(parent, orient="vertical", command=self.player_listbox.yview)
        self.player_listbox.configure(yscrollcommand=scrollbar_players.set)
        
        self.player_listbox.pack(side="left", fill="both", expand=True)
        scrollbar_players.pack(side="right", fill="y")
        
        # Bind events for enhanced interaction
        self.player_listbox.bind('<Button-1>', self._on_player_select)
        self.player_listbox.bind('<Double-Button-1>', self._on_player_double_click)
        self.player_listbox.bind('<B1-Motion>', self._on_player_drag)
        self.player_listbox.bind('<ButtonRelease-1>', self._on_player_drop)
        self.player_listbox.bind('<Enter>', self._on_player_hover_enter)
        self.player_listbox.bind('<Leave>', self._on_player_hover_leave)
        
        # Initialize player list
        self._update_player_browser()

    def _create_ai_optimization_panel(self, parent):
        """Create AI-powered optimization panel for Stage 4"""
        ai_label = ttk.Label(parent, text="AI Coach Assistant", style='Heading.TLabel')
        ai_label.pack(pady=(16, 8), anchor="w", padx=4)

        # AI optimization options
        ai_frame = ttk.Frame(parent, style='Panel.TFrame')
        ai_frame.pack(fill="x", pady=(0, 10))

        # Quick AI actions
        ttk.Button(ai_frame, text="Quick Optimize", command=self.ai_quick_optimize,
                  style='Secondary.TButton', width=15).pack(fill="x", pady=2)
        ttk.Button(ai_frame, text="Chemistry Focus", command=self.ai_chemistry_optimize,
                  style='Secondary.TButton', width=15).pack(fill="x", pady=2)
        ttk.Button(ai_frame, text="Balance Lines", command=self.ai_balance_optimize,
                  style='Secondary.TButton', width=15).pack(fill="x", pady=2)
        ttk.Button(ai_frame, text="Matchup Mode", command=self.ai_matchup_optimize,
                  style='Secondary.TButton', width=15).pack(fill="x", pady=2)
        
        # AI insights
        insights_frame = ttk.LabelFrame(parent, text="AI Insights", style='Panel.TLabelframe')
        insights_frame.pack(fill="x", pady=(10, 0))
        
        self.ai_insights_text = tk.Text(insights_frame, height=6, width=25,
                                       background=self.parent.CONTENT_BG,
                                       foreground=self.parent.TEXT_COLOR,
                                       font=(self.parent.FONT_FAMILY, 9),
                                       wrap=tk.WORD)
        ai_scrollbar = ttk.Scrollbar(insights_frame, orient="vertical", 
                                    command=self.ai_insights_text.yview)
        self.ai_insights_text.configure(yscrollcommand=ai_scrollbar.set)
        
        self.ai_insights_text.pack(side="left", fill="both", expand=True)
        ai_scrollbar.pack(side="right", fill="y")
        
        # Initialize AI insights
        self._update_ai_insights()

    def _create_enhanced_button_panel(self, parent):
        """Create button panel: one primary action, everything else quiet."""
        btn_frame = ttk.Frame(parent, style='Panel.TFrame')
        btn_frame.pack(fill="x", pady=(10, 0))

        # Primary actions
        primary_frame = ttk.Frame(btn_frame, style='Panel.TFrame')
        primary_frame.pack(side="left", fill="x", expand=True)

        ttk.Button(primary_frame, text="Save Lines", command=self.save_lines,
                  style='TButton').pack(side="left", padx=(0, 6))
        ttk.Button(primary_frame, text="Optimize", command=self.auto_optimize_lines,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(primary_frame, text="Reset", command=self.reset_lines,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(primary_frame, text="Swap Players", command=self.enter_swap_mode,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(primary_frame, text="Compare", command=self.enter_comparison_mode,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))
        ttk.Button(primary_frame, text="Smart Build", command=self.ai_smart_build,
                  style='Secondary.TButton').pack(side="left", padx=(0, 6))

        # Secondary actions
        secondary_frame = ttk.Frame(btn_frame, style='Panel.TFrame')
        secondary_frame.pack(side="right")

        ttk.Button(secondary_frame, text="Check Chemistry", command=self.check_chemistry,
                  style='Secondary.TButton').pack(side="left", padx=(6, 0))
        ttk.Button(secondary_frame, text="Full Analysis", command=self.show_full_analysis,
                  style='Secondary.TButton').pack(side="left", padx=(6, 0))
        ttk.Button(secondary_frame, text="Simulate", command=self.simulate_lineup_performance,
                  style='Secondary.TButton').pack(side="left", padx=(6, 0))

    def _load_current_lineup(self):
        """Load current lineup data into the interface"""
        try:
            # Populate forward lines
            for i in range(4):
                for j in range(3):
                    if i < len(self.lineup['Forwards']) and j < len(self.lineup['Forwards'][i]) and self.lineup['Forwards'][i][j]:
                        player = self.lineup['Forwards'][i][j]
                        self.fw_vars[i][j].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.fw_vars[i][j].set("")
            
            # Populate defense pairs
            for i in range(4):
                for j in range(2):
                    if i < len(self.lineup['Defense']) and j < len(self.lineup['Defense'][i]) and self.lineup['Defense'][i][j]:
                        player = self.lineup['Defense'][i][j]
                        self.df_vars[i][j].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.df_vars[i][j].set("")
            
            # Populate goalies
            for i in range(2):
                if i < len(self.lineup['Goalies']) and self.lineup['Goalies'][i]:
                    player = self.lineup['Goalies'][i]
                    self.g_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                else:
                    self.g_vars[i].set("None")
            
            # Populate power play units
            if 'PP1' in self.lineup and 'Forwards' in self.lineup['PP1']:
                for i in range(min(3, len(self.lineup['PP1']['Forwards']))):
                    if self.lineup['PP1']['Forwards'][i]:
                        player = self.lineup['PP1']['Forwards'][i]
                        self.pp1_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.pp1_fw_vars[i].set("")
                        
            if 'PP2' in self.lineup and 'Forwards' in self.lineup['PP2']:
                for i in range(min(3, len(self.lineup['PP2']['Forwards']))):
                    if self.lineup['PP2']['Forwards'][i]:
                        player = self.lineup['PP2']['Forwards'][i]
                        self.pp2_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.pp2_fw_vars[i].set("")
            
            # Populate defense for PP units
            if 'PP1' in self.lineup and 'Defense' in self.lineup['PP1']:
                for i in range(min(2, len(self.lineup['PP1']['Defense']))):
                    if self.lineup['PP1']['Defense'][i]:
                        player = self.lineup['PP1']['Defense'][i]
                        self.pp1_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.pp1_df_vars[i].set("")
                        
            if 'PP2' in self.lineup and 'Defense' in self.lineup['PP2']:
                for i in range(min(2, len(self.lineup['PP2']['Defense']))):
                    if self.lineup['PP2']['Defense'][i]:
                        player = self.lineup['PP2']['Defense'][i]
                        self.pp2_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                    else:
                        self.pp2_df_vars[i].set("")
            
            # Populate penalty kill units
            if 'PK1' in self.lineup:
                if 'Forwards' in self.lineup['PK1']:
                    for i in range(min(2, len(self.lineup['PK1']['Forwards']))):
                        if self.lineup['PK1']['Forwards'][i]:
                            player = self.lineup['PK1']['Forwards'][i]
                            self.pk1_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                        else:
                            self.pk1_fw_vars[i].set("")
                
                if 'Defense' in self.lineup['PK1']:
                    for i in range(min(2, len(self.lineup['PK1']['Defense']))):
                        if self.lineup['PK1']['Defense'][i]:
                            player = self.lineup['PK1']['Defense'][i]
                            self.pk1_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                        else:
                            self.pk1_df_vars[i].set("")
            
            if 'PK2' in self.lineup:
                if 'Forwards' in self.lineup['PK2']:
                    for i in range(min(2, len(self.lineup['PK2']['Forwards']))):
                        if self.lineup['PK2']['Forwards'][i]:
                            player = self.lineup['PK2']['Forwards'][i]
                            self.pk2_fw_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                        else:
                            self.pk2_fw_vars[i].set("")
                
                if 'Defense' in self.lineup['PK2']:
                    for i in range(min(2, len(self.lineup['PK2']['Defense']))):
                        if self.lineup['PK2']['Defense'][i]:
                            player = self.lineup['PK2']['Defense'][i]
                            self.pk2_df_vars[i].set(f"{player.full_name} ({player.primary_position.value}) - {player.overall_rating()}")
                        else:
                            self.pk2_df_vars[i].set("")
            
            print("Lineup loaded successfully!")
            
        except Exception as e:
            print(f"Error loading current lineup: {e}")
            # Initialize all variables with empty values on error
            for i in range(4):
                for j in range(3):
                    self.fw_vars[i][j].set("")
            for i in range(3):
                for j in range(2):
                    self.df_vars[i][j].set("")
            for i in range(2):
                self.g_vars[i].set("None")
                self.pp1_fw_vars[i].set("")
                self.pp1_df_vars[i].set("")
                self.pp2_fw_vars[i].set("")
                self.pp2_df_vars[i].set("")
                self.pk1_fw_vars[i].set("")
                self.pk1_df_vars[i].set("")
                self.pk2_fw_vars[i].set("")
                self.pk2_df_vars[i].set("")
            if len(self.pp1_fw_vars) > 2:
                self.pp1_fw_vars[2].set("")
            if len(self.pp2_fw_vars) > 2:
                self.pp2_fw_vars[2].set("")

    def _bind_enhanced_events(self):
        """Bind enhanced events for Stage 2 interactivity"""
        # Bind notebook tab changes for real-time updates (disabled for stability)
        # self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Bind window events
        self.bind("<Key>", self._on_key_press)
        self.bind("<Control-z>", lambda e: self.undo_action())
        self.bind("<Control-y>", lambda e: self.redo_action())
        self.bind("<Control-s>", lambda e: self.save_lines(silent=True))
        
        # Make window focusable for keyboard events
        self.focus_set()

    def _start_real_time_updates(self):
        """Start real-time analytics updates"""
        if hasattr(self, 'analytics_enabled') and self.analytics_enabled:
            if hasattr(self, '_update_real_time_analytics'):
                self._update_real_time_analytics()
            # Schedule next update
            self.after(2000, self._start_real_time_updates)
    
    def _update_real_time_analytics(self):
        """Update real-time analytics - placeholder implementation"""
        pass
    
    def _update_context_analytics(self, tab_text):
        """Update analytics based on current tab"""
        pass

    def _on_tab_changed(self, event):
        """Handle tab change events"""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        
        # Update analytics based on current tab
        if "Analytics" in tab_text:
            if hasattr(self, '_update_full_analytics'):
                self._update_full_analytics()
        else:
            if hasattr(self, '_update_context_analytics'):
                self._update_context_analytics(tab_text)

    def _on_key_press(self, event):
        """Handle keyboard shortcuts"""
        if event.state & 0x4:  # Ctrl key
            if event.keysym == 'z':
                self.undo_action()
            elif event.keysym == 'y':
                self.redo_action()
            elif event.keysym == 's':
                self.save_lines(silent=True)

    def _on_tab_click(self, event, tab_name):
        """Handle tab click for drag-and-drop initiation"""
        self.drag_source = tab_name
        self.drag_mode = False

    def _on_tab_drag(self, event, tab_name):
        """Handle tab drag motion"""
        if self.drag_source:
            self.drag_mode = True

    def _on_tab_drop(self, event, tab_name):
        """Handle tab drop for drag-and-drop completion"""
        if self.drag_mode and self.drag_source:
            # Implement drag-and-drop logic here
            pass
        self.drag_source = None
        self.drag_mode = False

    # Stage 3: Advanced drag-and-drop and visual functionality
    def _initialize_drag_drop_system(self):
        """Initialize advanced drag-and-drop system"""
        self.drop_zones = {
            'even_strength': {},
            'power_play': {},
            'penalty_kill': {},
            'goalies': {}
        }

    def _initialize_visual_effects(self):
        """Initialize visual effects system"""
        self.visual_timers = []
        self.highlight_widgets = []

    def _create_player_cards(self):
        """Create enhanced player cards with detailed information"""
        self.player_cards = {}

    def _bind_stage3_events(self):
        """Bind Stage 3 advanced events"""
        # Inherit Stage 2 events
        self._bind_enhanced_events()

    def _on_selection_mode_change(self, event=None):
        """Handle selection mode changes"""
        if hasattr(self, 'selection_mode_var'):
            self.player_selection_mode = self.selection_mode_var.get()
        if hasattr(self, 'selected_players'):
            self.selected_players.clear()

    def _toggle_animations(self):
        """Toggle animation effects"""
        if hasattr(self, 'animations_var'):
            self.visual_effects['animations'] = self.animations_var.get()

    def _toggle_chemistry_viz(self):
        """Toggle chemistry visualization"""
        if hasattr(self, 'chemistry_viz_var'):
            self.chemistry_visualization = self.chemistry_viz_var.get()

    def _on_filter_change(self, event=None):
        """Handle filter changes in player browser"""
        self._update_player_browser()

    def _update_player_browser(self):
        """Update the player browser with filtered results"""
        if not hasattr(self, 'player_listbox'):
            return
            
        # Clear current list
        self.player_listbox.delete(0, tk.END)
        
        # Apply filters
        filtered_players = self._apply_player_filters()
        
        # Sort players
        filtered_players.sort(key=self._get_sort_key, reverse=True)
        
        # Add to listbox with enhanced formatting
        for player in filtered_players:
            display_text = self._format_player_display(player)
            self.player_listbox.insert(tk.END, display_text)

    def _apply_player_filters(self):
        """Apply current filters to player list"""
        filtered = []
        
        for player in self.roster:
            # Position filter
            if hasattr(self, 'position_filter_var'):
                pos_filter = self.position_filter_var.get()
                if pos_filter != "all" and player.primary_position.value != pos_filter:
                    continue
            
            # Rating filter
            if hasattr(self, 'rating_filter_var'):
                rating_filter = self.rating_filter_var.get()
                overall = player.overall_rating()
                
                if rating_filter == "85+" and overall < 85:
                    continue
                elif rating_filter == "80-84" and not (80 <= overall < 85):
                    continue
                elif rating_filter == "75-79" and not (75 <= overall < 80):
                    continue
                elif rating_filter == "70-74" and not (70 <= overall < 75):
                    continue
                elif rating_filter == "<70" and overall >= 70:
                    continue
            
            filtered.append(player)
        
        return filtered

    def _get_sort_key(self, player):
        """Get sort key for player ordering"""
        if self.sorting_criteria == 'overall':
            return player.overall_rating()
        elif self.sorting_criteria == 'name':
            return player.full_name
        else:
            return getattr(player, self.sorting_criteria, 0)

    def _format_player_display(self, player):
        """Format player for display in browser"""
        overall = player.overall_rating()
        pos = player.primary_position.value
        
        # Add visual indicators
        quality_indicator = self._get_quality_indicator(overall)
        status_indicator = self._get_player_status_indicator(player)
        
        return f"{quality_indicator} {player.full_name} ({pos}, {overall:.0f}) {status_indicator}"

    def _get_quality_indicator(self, overall):
        """Get visual quality indicator for player"""
        if overall >= 85:
            return "⭐"  # Elite
        elif overall >= 80:
            return "🔸"  # Star
        elif overall >= 75:
            return "🔹"  # Good
        elif overall >= 70:
            return "▫️"  # Average
        else:
            return "▪️"  # Depth

    def _get_player_status_indicator(self, player):
        """Get status indicator for player (injured, in lineup, etc.)"""
        # Check if player is in current lineup
        if self._is_player_in_lineup(player):
            return "✓"
        return ""

    def _is_player_in_lineup(self, player):
        """Check if player is currently in the lineup"""
        # Check all lineup positions
        for line in self.lineup['Forwards']:
            if player in line:
                return True
        for pair in self.lineup['Defense']:
            if player in pair:
                return True
        if player in self.lineup['Goalies']:
            return True
        return False

    def _on_player_select(self, event):
        """Handle player selection in browser"""
        if not hasattr(self, 'player_listbox'):
            return
        selection = self.player_listbox.curselection()
        if selection:
            index = selection[0]
            filtered_players = self._apply_player_filters()
            if index < len(filtered_players):
                player = filtered_players[index]
                self._handle_player_selection(player)

    def _on_player_double_click(self, event):
        """Handle double-click on player"""
        if not hasattr(self, 'player_listbox'):
            return
        selection = self.player_listbox.curselection()
        if selection:
            index = selection[0]
            filtered_players = self._apply_player_filters()
            if index < len(filtered_players):
                player = filtered_players[index]
                self._show_player_details(player)

    def _on_player_drag(self, event):
        """Handle player drag start"""
        pass  # Placeholder for drag functionality

    def _on_player_drop(self, event):
        """Handle player drop"""
        pass  # Placeholder for drop functionality

    def _on_player_hover_enter(self, event):
        """Handle mouse enter on player browser"""
        self.hover_effects = True

    def _on_player_hover_leave(self, event):
        """Handle mouse leave on player browser"""
        self.hover_effects = False

    def enter_swap_mode(self):
        """Enter player swap mode"""
        if not hasattr(self, 'selected_players'):
            self.selected_players = []
        self.player_selection_mode = 'swap'
        if hasattr(self, 'selection_mode_var'):
            self.selection_mode_var.set('swap')
        self.selected_players.clear()
        tk.messagebox.showinfo("Swap Mode", "Select two players to swap their positions.")

    def enter_comparison_mode(self):
        """Enter player comparison mode"""
        if not hasattr(self, 'selected_players'):
            self.selected_players = []
        self.comparison_mode = True
        self.selected_players.clear()
        tk.messagebox.showinfo("Comparison Mode", "Select players to compare their statistics.")

    def _handle_player_selection(self, player):
        """Handle player selection based on current mode"""
        if not hasattr(self, 'selected_players'):
            self.selected_players = []
            
        if self.player_selection_mode == 'single':
            self.selected_players = [player]
        elif self.player_selection_mode == 'multi':
            if player not in self.selected_players:
                self.selected_players.append(player)
        elif self.player_selection_mode == 'swap':
            if player not in self.selected_players:
                self.selected_players.append(player)
                if len(self.selected_players) == 2:
                    self._perform_player_swap()

    def _perform_player_swap(self):
        """Perform swap between two selected players"""
        if len(self.selected_players) == 2:
            player1, player2 = self.selected_players
            
            # Find positions of both players in lineup
            pos1 = self._find_player_position(player1)
            pos2 = self._find_player_position(player2)
            
            if pos1 and pos2:
                # Perform the swap
                self._save_undo_state()
                self._swap_player_positions(pos1, pos2)
                self._mark_changes()
                if hasattr(self, '_update_analytics_display'):
                    self._update_analytics_display()
                
                tk.messagebox.showinfo("Swap Complete", 
                    f"Swapped {player1.full_name} and {player2.full_name}")
            
            # Reset swap mode
            self.selected_players.clear()

    def _find_player_position(self, player):
        """Find a player's position in the current lineup"""
        # Check forwards
        for i, line in enumerate(self.lineup['Forwards']):
            for j, p in enumerate(line):
                if p == player:
                    return ('Forwards', i, j)
        
        # Check defense
        for i, pair in enumerate(self.lineup['Defense']):
            for j, p in enumerate(pair):
                if p == player:
                    return ('Defense', i, j)
        
        # Check goalies
        for i, p in enumerate(self.lineup['Goalies']):
            if p == player:
                return ('Goalies', i)
        
        return None

    def _swap_player_positions(self, pos1, pos2):
        """Swap players at two positions in the lineup"""
        # Extract position details
        if len(pos1) == 3:  # Forwards or Defense
            type1, line1, slot1 = pos1
            player1 = self.lineup[type1][line1][slot1]
        else:  # Goalies
            type1, slot1 = pos1
            player1 = self.lineup[type1][slot1]
        
        if len(pos2) == 3:  # Forwards or Defense
            type2, line2, slot2 = pos2
            player2 = self.lineup[type2][line2][slot2]
        else:  # Goalies
            type2, slot2 = pos2
            player2 = self.lineup[type2][slot2]
        
        # Perform the swap
        if len(pos1) == 3:
            self.lineup[type1][line1][slot1] = player2
        else:
            self.lineup[type1][slot1] = player2
            
        if len(pos2) == 3:
            self.lineup[type2][line2][slot2] = player1
        else:
            self.lineup[type2][slot2] = player1

    def _show_player_details(self, player):
        """Show detailed player information window"""
        detail_window = tk.Toplevel(self)
        detail_window.title(f"Player Details - {player.full_name}")
        detail_window.geometry("400x500")
        detail_window.configure(background=self.parent.BG_COLOR)
        
        # Create scrollable frame for player details
        canvas = tk.Canvas(detail_window, background=self.parent.CONTENT_BG)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add player information
        self._populate_player_details(scrollable_frame, player)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _populate_player_details(self, parent, player):
        """Populate player details in the detail window"""
        # Basic info
        info_frame = ttk.LabelFrame(parent, text="Basic Information", style='Panel.TLabelframe')
        info_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Name: {player.full_name}", style='TLabel').pack(anchor="w", padx=10, pady=2)
        ttk.Label(info_frame, text=f"Position: {player.primary_position.value}", style='TLabel').pack(anchor="w", padx=10, pady=2)
        ttk.Label(info_frame, text=f"Age: {player.age}", style='TLabel').pack(anchor="w", padx=10, pady=2)
        ttk.Label(info_frame, text=f"Overall: {player.overall_rating():.1f}", style='TLabel').pack(anchor="w", padx=10, pady=2)
        
        # Attributes
        attr_frame = ttk.LabelFrame(parent, text="Attributes", style='Panel.TLabelframe')
        attr_frame.pack(fill="x", padx=10, pady=5)
        
        # Display key attributes based on position
        key_attrs = self._get_key_attributes_for_position(player.primary_position.value)
        for attr_name in key_attrs:
            value = getattr(player, attr_name, 0)
            display_name = attr_name.replace('_', ' ').title()
            ttk.Label(attr_frame, text=f"{display_name}: {value}", style='TLabel').pack(anchor="w", padx=10, pady=1)

    def _get_key_attributes_for_position(self, position):
        """Get key attributes to display for a position"""
        if position == 'G':
            return ['goaltending', 'reflexes', 'positioning', 'rebound_control']
        elif position in ['C', 'LW', 'RW']:
            return ['shooting', 'passing', 'skating', 'hockey_iq', 'checking']
        else:  # Defense
            return ['defense', 'passing', 'skating', 'checking', 'hockey_iq']

    # Stage 4: Advanced AI and optimization methods
    def _initialize_ai_optimization_engine(self):
        """Initialize AI optimization engine"""
        self.ai_engine = {
            'chemistry_weights': {'skill_balance': 0.3, 'personality': 0.2, 'experience': 0.2, 'style': 0.3},
            'optimization_priorities': ['overall_strength', 'chemistry', 'balance', 'matchups'],
            'learning_enabled': True
        }

    def _initialize_predictive_analytics(self):
        """Initialize predictive analytics system"""
        self.prediction_models = {
            'performance': True,
            'chemistry': True,
            'fatigue': True,
            'matchup_success': True
        }

    def _initialize_interactive_features(self):
        """Initialize interactive features (without ice surface)"""
        self.interactive_elements = {
            'hover_effects': True,
            'contextual_menus': True,
            'real_time_feedback': True
        }

    # def _build_interactive_ice_surface_tab(self):
    #     """Build interactive ice surface tab for Stage 4 - DISABLED"""
    #     # Removed - focusing on clean line editing interface
    #     pass

    # def _draw_ice_surface(self):
    #     """Draw the hockey ice surface with positions - DISABLED"""
    #     pass

    # def _draw_position_slots(self):
    #     """Draw draggable position slots on ice - DISABLED"""
    #     pass

    # def _create_position_slot(self, x, y, position, player_type):
    #     """Create a draggable position slot - DISABLED"""
    #     pass

    def ai_optimize_lineup(self):
        """AI-powered lineup optimization"""
        self._save_undo_state()
        
        # Advanced AI optimization algorithm
        optimization_result = self._run_ai_optimization()
        
        if optimization_result['success']:
            self.lineup = optimization_result['lineup']
            self._mark_changes()
            self._update_analytics_display()
            self._update_ai_insights()
            
            tk.messagebox.showinfo("AI Optimization Complete", 
                f"Lineup optimized with {optimization_result['improvements']} improvements")
        else:
            tk.messagebox.showwarning("AI Optimization", "Unable to improve current lineup significantly")

    def _run_ai_optimization(self):
        """Run advanced AI optimization algorithm"""
        import random
        
        # Simulate AI optimization
        current_score = self._calculate_lineup_score()
        best_lineup = dict(self.lineup)
        best_score = current_score
        improvements = 0
        
        # Try different optimization strategies
        for strategy in ['chemistry', 'balance', 'matchup']:
            test_lineup = self._optimize_by_strategy(strategy)
            test_score = self._calculate_lineup_score(test_lineup)
            
            if test_score > best_score:
                best_lineup = test_lineup
                best_score = test_score
                improvements += 1
        
        return {
            'success': improvements > 0,
            'lineup': best_lineup,
            'improvements': improvements,
            'score_improvement': best_score - current_score
        }

    def _optimize_by_strategy(self, strategy):
        """Optimize lineup by specific strategy"""
        import copy
        import random
        
        test_lineup = copy.deepcopy(self.lineup)
        
        if strategy == 'chemistry':
            # Optimize for chemistry
            self._optimize_chemistry(test_lineup)
        elif strategy == 'balance':
            # Optimize for balance
            self._optimize_balance(test_lineup)
        elif strategy == 'matchup':
            # Optimize for matchups
            self._optimize_matchups(test_lineup)
        
        return test_lineup

    def _optimize_chemistry(self, lineup):
        """Optimize lineup for chemistry"""
        # Simple chemistry optimization - group players with similar play styles
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: (p.overall_rating(), getattr(p, 'hockey_iq', 10)), reverse=True)
        
        # Redistribute based on chemistry factors
        for i, line in enumerate(lineup['Forwards']):
            start_idx = i * 3
            end_idx = start_idx + 3
            if end_idx <= len(forwards):
                lineup['Forwards'][i] = forwards[start_idx:end_idx]

    def _optimize_balance(self, lineup):
        """Optimize lineup for balance"""
        # Balance lines by spreading talent evenly
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Distribute top players across lines
        for pos in range(3):  # LW, C, RW
            players_by_pos = [p for p in forwards[pos::3]]
            for line in range(4):
                if line < len(players_by_pos):
                    lineup['Forwards'][line][pos] = players_by_pos[line]

    def _optimize_matchups(self, lineup):
        """Optimize lineup for matchups"""
        # Focus on creating strong top lines for key matchups
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Load top line with best players
        if len(forwards) >= 3:
            lineup['Forwards'][0] = forwards[:3]
        
        # Balance remaining lines
        remaining = forwards[3:]
        for i in range(1, 4):
            start_idx = (i-1) * 3
            end_idx = start_idx + 3
            if end_idx <= len(remaining):
                lineup['Forwards'][i] = remaining[start_idx:end_idx]

    def _calculate_lineup_score(self, lineup=None):
        """Calculate overall lineup effectiveness score"""
        if lineup is None:
            lineup = self.lineup
        
        score = 0
        
        # Score forward lines
        for line in lineup['Forwards']:
            players = [p for p in line if p]
            if players:
                line_avg = sum(p.overall_rating() for p in players) / len(players)
                chemistry_bonus = self._calculate_line_chemistry(players)
                score += line_avg + chemistry_bonus
        
        # Score defense pairs
        for pair in lineup['Defense']:
            players = [p for p in pair if p]
            if players:
                pair_avg = sum(p.overall_rating() for p in players) / len(players)
                score += pair_avg
        
        # Score goalies
        goalies = [g for g in lineup['Goalies'] if g]
        if goalies:
            score += goalies[0].overall_rating()  # Starter rating
        
        return score

    def show_performance_prediction(self):
        """Show AI performance prediction for current lineup"""
        prediction_window = tk.Toplevel(self)
        prediction_window.title("🔮 Performance Prediction")
        prediction_window.geometry("500x400")
        prediction_window.configure(background=self.parent.BG_COLOR)
        
        # Create prediction content
        main_frame = ttk.Frame(prediction_window, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="🔮 AI Performance Prediction", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Generate predictions
        predictions = self._generate_performance_predictions()
        
        # Display predictions
        for category, prediction in predictions.items():
            frame = ttk.LabelFrame(main_frame, text=category, style='Panel.TLabelframe')
            frame.pack(fill="x", pady=5)
            
            ttk.Label(frame, text=prediction, style='TLabel').pack(anchor="w", padx=10, pady=5)

    def _generate_performance_predictions(self):
        """Generate AI performance predictions"""
        lineup_score = self._calculate_lineup_score()
        
        predictions = {
            "Overall Effectiveness": f"Lineup rated {lineup_score:.1f}/100 - {'Excellent' if lineup_score > 85 else 'Good' if lineup_score > 75 else 'Average'}",
            "Offensive Potential": f"Expected goals per game: {2.5 + (lineup_score - 75) * 0.1:.1f}",
            "Defensive Stability": f"Expected goals against: {2.8 - (lineup_score - 75) * 0.05:.1f}",
            "Chemistry Rating": f"Line chemistry: {self._calculate_overall_chemistry():.1f}%",
            "Fatigue Management": "Balanced ice time distribution - Low fatigue risk",
            "Special Teams": "Power play efficiency: Above average, Penalty kill: Solid"
        }
        
        return predictions

    def _calculate_overall_chemistry(self):
        """Calculate overall team chemistry"""
        total_chemistry = 0
        line_count = 0
        
        # Forward line chemistry
        for line in self.lineup['Forwards']:
            players = [p for p in line if p]
            if len(players) >= 2:
                total_chemistry += self._calculate_line_chemistry(players)
                line_count += 1
        
        # Defense pair chemistry
        for pair in self.lineup['Defense']:
            players = [p for p in pair if p]
            if len(players) >= 2:
                total_chemistry += self._calculate_line_chemistry(players)
                line_count += 1
        
        return total_chemistry / line_count if line_count > 0 else 50

    def optimize_for_matchup(self):
        """Optimize lineup for specific matchup"""
        matchup_window = tk.Toplevel(self)
        matchup_window.title("🎯 Matchup Optimizer")
        matchup_window.geometry("400x300")
        matchup_window.configure(background=self.parent.BG_COLOR)
        
        main_frame = ttk.Frame(matchup_window, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Optimize for Matchup", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Matchup options
        ttk.Label(main_frame, text="Select opposing team style:", style='TLabel').pack(anchor="w")
        
        self.matchup_style_var = tk.StringVar(master=self, value="Balanced")
        style_combo = ttk.Combobox(main_frame, textvariable=self.matchup_style_var,
                                  values=["Speed/Skill", "Physical", "Defensive", "Balanced"],
                                  state="readonly")
        style_combo.pack(fill="x", pady=(5, 10))
        
        ttk.Label(main_frame, text="Optimization focus:", style='TLabel').pack(anchor="w")
        
        self.matchup_focus_var = tk.StringVar(master=self, value="Offensive")
        focus_combo = ttk.Combobox(main_frame, textvariable=self.matchup_focus_var,
                                  values=["Offensive", "Defensive", "Neutral Zone", "Special Teams"],
                                  state="readonly")
        focus_combo.pack(fill="x", pady=(5, 20))
        
        ttk.Button(main_frame, text="🎯 Optimize Lineup", 
                  command=lambda: self._apply_matchup_optimization(matchup_window),
                  style='TButton').pack()

    def _apply_matchup_optimization(self, window):
        """Apply matchup-specific optimization"""
        self._save_undo_state()
        
        style = self.matchup_style_var.get()
        focus = self.matchup_focus_var.get()
        
        # Apply optimization based on matchup
        if focus == "Offensive":
            self._optimize_for_offense()
        elif focus == "Defensive":
            self._optimize_for_defense()
        elif focus == "Special Teams":
            self._optimize_special_teams()
        
        self._mark_changes()
        self._update_analytics_display()
        
        window.destroy()
        tk.messagebox.showinfo("Matchup Optimization", 
                              f"Lineup optimized for {style} opponent with {focus} focus")

    def _optimize_for_offense(self):
        """Optimize lineup for offensive play"""
        # Load top lines with best offensive players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: getattr(p, 'shooting', 10) + getattr(p, 'passing', 10), reverse=True)
        
        # Distribute top offensive players
        for i in range(min(3, len(self.lineup['Forwards']))):
            start_idx = i * 3
            end_idx = start_idx + 3
            if end_idx <= len(forwards):
                self.lineup['Forwards'][i] = forwards[start_idx:end_idx]

    def _optimize_for_defense(self):
        """Optimize lineup for defensive play"""
        # Prioritize defensive-minded players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: getattr(p, 'checking', 10) + getattr(p, 'defense', 10), reverse=True)
        
        # Load defensive specialists on checking lines
        for i in range(2, min(4, len(self.lineup['Forwards']))):
            start_idx = i * 3
            end_idx = start_idx + 3
            if end_idx <= len(forwards):
                self.lineup['Forwards'][i] = forwards[start_idx:end_idx]

    def _optimize_special_teams(self):
        """Optimize special teams units"""
        # Optimize power play for skill
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: getattr(p, 'shooting', 10) + getattr(p, 'passing', 10) + getattr(p, 'vision', 10), reverse=True)
        
        if len(forwards) >= 6:
            self.lineup['PP1']['Forwards'] = forwards[:3]
            self.lineup['PP2']['Forwards'] = forwards[3:6]

    def ai_quick_optimize(self):
        """Quick AI optimization"""
        self._save_undo_state()
        self.auto_optimize_lines()
        self._update_ai_insights()

    def ai_chemistry_optimize(self):
        """AI chemistry-focused optimization"""
        self._save_undo_state()
        test_lineup = dict(self.lineup)
        self._optimize_chemistry(test_lineup)
        self.lineup = test_lineup
        self._mark_changes()
        self._update_analytics_display()
        tk.messagebox.showinfo("Chemistry Optimization", "Lineup optimized for maximum chemistry!")

    def ai_balance_optimize(self):
        """AI balance-focused optimization"""
        self._save_undo_state()
        test_lineup = dict(self.lineup)
        self._optimize_balance(test_lineup)
        self.lineup = test_lineup
        self._mark_changes()
        self._update_analytics_display()
        tk.messagebox.showinfo("Balance Optimization", "Lineup optimized for balanced scoring!")

    def ai_matchup_optimize(self):
        """AI matchup-focused optimization"""
        self.optimize_for_matchup()

    def ai_smart_build(self):
        """AI smart lineup building"""
        smart_window = tk.Toplevel(self)
        smart_window.title("🎯 Smart Lineup Builder")
        smart_window.geometry("450x350")
        smart_window.configure(background=self.parent.BG_COLOR)
        
        main_frame = ttk.Frame(smart_window, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="🎯 AI Smart Lineup Builder", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Smart build options
        options_frame = ttk.LabelFrame(main_frame, text="Build Parameters", style='Panel.TLabelframe')
        options_frame.pack(fill="x", pady=(0, 10))
        
        # Team style
        ttk.Label(options_frame, text="Team Style:", style='TLabel').pack(anchor="w", padx=10, pady=(10, 0))
        self.team_style_var = tk.StringVar(master=self, value="Balanced")
        ttk.Combobox(options_frame, textvariable=self.team_style_var,
                    values=["Speed & Skill", "Physical", "Defensive", "Balanced"],
                    state="readonly").pack(fill="x", padx=10, pady=(5, 10))
        
        # Priority
        ttk.Label(options_frame, text="Priority:", style='TLabel').pack(anchor="w", padx=10)
        self.priority_var = tk.StringVar(master=self, value="Overall Strength")
        ttk.Combobox(options_frame, textvariable=self.priority_var,
                    values=["Overall Strength", "Chemistry", "Youth Development", "Veteran Leadership"],
                    state="readonly").pack(fill="x", padx=10, pady=(5, 10))
        
        # Actions
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=10)
        
        ttk.Button(action_frame, text="🚀 Build Lineup", 
                  command=lambda: self._execute_smart_build(smart_window),
                  style='TButton').pack(side="left", padx=(0, 10))
        ttk.Button(action_frame, text="❌ Cancel", 
                  command=smart_window.destroy,
                  style='TButton').pack(side="left")

    def _execute_smart_build(self, window):
        """Execute smart lineup building"""
        self._save_undo_state()
        
        style = self.team_style_var.get()
        priority = self.priority_var.get()
        
        # Build lineup based on parameters
        if priority == "Overall Strength":
            self.set_best_lines()
        elif priority == "Chemistry":
            self.ai_chemistry_optimize()
        elif priority == "Youth Development":
            self._build_youth_focused_lineup()
        elif priority == "Veteran Leadership":
            self._build_veteran_focused_lineup()
        
        self._mark_changes()
        self._update_analytics_display()
        self._update_ai_insights()
        
        window.destroy()
        tk.messagebox.showinfo("Smart Build Complete", 
                              f"Lineup built with {style} style, prioritizing {priority}")

    def _build_youth_focused_lineup(self):
        """Build lineup focusing on youth development"""
        # Prioritize younger players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: (25 - p.age, p.overall_rating()), reverse=True)
        
        # Mix youth with veterans
        for i, line in enumerate(self.lineup['Forwards']):
            start_idx = i * 3
            end_idx = start_idx + 3
            if end_idx <= len(forwards):
                self.lineup['Forwards'][i] = forwards[start_idx:end_idx]

    def _build_veteran_focused_lineup(self):
        """Build lineup focusing on veteran leadership"""
        # Prioritize experienced players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: (p.age if p.age >= 25 else 0, p.overall_rating()), reverse=True)
        
        for i, line in enumerate(self.lineup['Forwards']):
            start_idx = i * 3
            end_idx = start_idx + 3
            if end_idx <= len(forwards):
                self.lineup['Forwards'][i] = forwards[start_idx:end_idx]

    def simulate_lineup_performance(self):
        """Simulate lineup performance"""
        simulation_window = tk.Toplevel(self)
        simulation_window.title("🔮 Lineup Simulation")
        simulation_window.geometry("600x500")
        simulation_window.configure(background=self.parent.BG_COLOR)
        
        main_frame = ttk.Frame(simulation_window, style='Panel.TFrame')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="🔮 Lineup Performance Simulation", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Simulation results
        results_frame = ttk.LabelFrame(main_frame, text="Simulation Results", style='Panel.TLabelframe')
        results_frame.pack(fill="both", expand=True)
        
        # Generate simulation data
        sim_data = self._run_lineup_simulation()
        
        # Display results
        results_text = tk.Text(results_frame, wrap=tk.WORD,
                              background=self.parent.CONTENT_BG,
                              foreground=self.parent.TEXT_COLOR,
                              font=(self.parent.FONT_FAMILY, 10))
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=results_text.yview)
        results_text.configure(yscrollcommand=scrollbar.set)
        
        results_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Insert simulation results
        results_text.insert(tk.END, sim_data)
        results_text.configure(state="disabled")

    def _run_lineup_simulation(self):
        """Run lineup performance simulation"""
        import random
        
        lineup_score = self._calculate_lineup_score()
        chemistry = self._calculate_overall_chemistry()
        
        # Simulate 10 games
        results = []
        total_goals_for = 0
        total_goals_against = 0
        wins = 0
        
        for game in range(1, 11):
            # Simulate game based on lineup strength
            goals_for = random.randint(1, 6) + int((lineup_score - 75) / 10)
            goals_against = random.randint(1, 5) - int((chemistry - 50) / 20)
            goals_against = max(0, goals_against)
            
            total_goals_for += goals_for
            total_goals_against += goals_against
            
            if goals_for > goals_against:
                wins += 1
                result = "W"
            elif goals_for < goals_against:
                result = "L"
            else:
                result = "OT"
                wins += 0.5
            
            results.append(f"Game {game}: {goals_for}-{goals_against} {result}")
        
        # Summary
        summary = f"""🏒 LINEUP SIMULATION RESULTS (10 Games)
{'='*50}

TEAM PERFORMANCE:
Record: {int(wins)}-{10-int(wins)} ({wins/10*100:.1f}% win rate)
Goals For: {total_goals_for} ({total_goals_for/10:.1f} per game)
Goals Against: {total_goals_against} ({total_goals_against/10:.1f} per game)
Goal Differential: +{total_goals_for - total_goals_against}

LINEUP ANALYSIS:
Overall Rating: {lineup_score:.1f}/100
Chemistry Rating: {chemistry:.1f}%
Expected Performance: {'Excellent' if wins >= 7 else 'Good' if wins >= 5 else 'Average'}

GAME RESULTS:
{chr(10).join(results)}

RECOMMENDATIONS:
"""
        
        if wins >= 7:
            summary += "• Excellent lineup performance\n• Consider this your optimal configuration"
        elif wins >= 5:
            summary += "• Good lineup balance\n• Minor tweaks could improve performance"
        else:
            summary += "• Lineup needs improvement\n• Consider AI optimization or player changes"
        
        return summary

    def _update_ai_insights(self):
        """Update AI insights panel"""
        if not hasattr(self, 'ai_insights_text'):
            return
        
        insights = self._generate_ai_insights()
        
        self.ai_insights_text.configure(state="normal")
        self.ai_insights_text.delete(1.0, tk.END)
        self.ai_insights_text.insert(tk.END, insights)
        self.ai_insights_text.configure(state="disabled")

    def _generate_ai_insights(self):
        """Generate AI insights for current lineup"""
        lineup_score = self._calculate_lineup_score()
        chemistry = self._calculate_overall_chemistry()
        
        insights = f"""🤖 AI COACH INSIGHTS

LINEUP STRENGTH: {lineup_score:.1f}/100
{'⭐' * min(5, int(lineup_score/20))}

CHEMISTRY: {chemistry:.1f}%
{'🧪' * min(5, int(chemistry/20))}

"""
        
        # Add specific recommendations
        if lineup_score < 75:
            insights += "💡 Consider upgrading your top lines\n"
        if chemistry < 60:
            insights += "💡 Try chemistry-focused optimization\n"
        
        insights += f"\n🎯 QUICK TIPS:\n"
        insights += "• Use AI Optimize for best results\n"
        insights += "• Check chemistry regularly\n"
        insights += "• Balance skill across lines\n"
        insights += "• Consider matchup strategies"
        
        return insights

    # def _on_ice_click(self, event):
    #     """Handle ice surface click - DISABLED"""
    #     pass

    # def _on_ice_drag(self, event):
    #     """Handle ice surface drag - DISABLED"""
    #     pass

    # def _on_ice_drop(self, event):
    #     """Handle ice surface drop - DISABLED"""
    #     pass

    # def _on_ice_hover(self, event):
    #     """Handle ice surface hover - DISABLED"""
    #     pass

    def _optimize_single_line(self, line_index, line_type):
        """Optimize a single forward line or defense pair"""
        self._save_undo_state()
        
        if line_type == 'Forwards':
            # Get best available forwards for this line
            forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
            forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
            
            # Skip players already assigned to higher lines
            used_players = []
            for i in range(line_index):
                used_players.extend([p for p in self.lineup['Forwards'][i] if p])
            
            available = [p for p in forwards if p not in used_players]
            
            # Assign best 3 available players
            if len(available) >= 3:
                self.lineup['Forwards'][line_index] = available[:3]
                self._mark_changes()
                self._update_analytics_display()
                tk.messagebox.showinfo("Line Optimized", f"Forward line {line_index + 1} optimized!")
            else:
                tk.messagebox.showwarning("Insufficient Players", "Not enough available forwards to optimize this line.")
                
        elif line_type == 'Defense':
            # Get best available defensemen for this pair
            defensemen = [p for p in self.roster if p.primary_position.value in ['LD', 'RD', 'D']]
            defensemen.sort(key=lambda p: p.overall_rating(), reverse=True)
            
            # Skip players already assigned to higher pairs
            used_players = []
            for i in range(line_index):
                used_players.extend([p for p in self.lineup['Defense'][i] if p])
            
            available = [p for p in defensemen if p not in used_players]
            
            # Assign best 2 available players
            if len(available) >= 2:
                self.lineup['Defense'][line_index] = available[:2]
                self._mark_changes()
                self._update_analytics_display()
                tk.messagebox.showinfo("Pair Optimized", f"Defense pair {line_index + 1} optimized!")
            else:
                tk.messagebox.showwarning("Insufficient Players", "Not enough available defensemen to optimize this pair.")

    def _optimize_power_play_unit(self, unit_num):
        """Optimize a power play unit"""
        self._save_undo_state()
        
        # Get best offensive players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        defensemen = [p for p in self.roster if p.primary_position.value in ['LD', 'RD', 'D']]
        
        # Sort by offensive skills
        forwards.sort(key=lambda p: getattr(p, 'shooting', 10) + getattr(p, 'passing', 10) + getattr(p, 'vision', 10), reverse=True)
        defensemen.sort(key=lambda p: getattr(p, 'passing', 10) + getattr(p, 'shooting', 10) + getattr(p, 'vision', 10), reverse=True)
        
        unit_key = f'PP{unit_num}'
        
        # Skip players used in higher units
        used_forwards = []
        used_defense = []
        
        for i in range(1, unit_num):
            other_unit = f'PP{i}'
            if other_unit in self.lineup:
                used_forwards.extend([p for p in self.lineup[other_unit]['Forwards'] if p])
                used_defense.extend([p for p in self.lineup[other_unit]['Defense'] if p])
        
        # Get available players
        available_forwards = [p for p in forwards if p not in used_forwards]
        available_defense = [p for p in defensemen if p not in used_defense]
        
        # Assign best available players
        if len(available_forwards) >= 3 and len(available_defense) >= 2:
            self.lineup[unit_key]['Forwards'] = available_forwards[:3]
            self.lineup[unit_key]['Defense'] = available_defense[:2]
            self._mark_changes()
            self._update_analytics_display()
            tk.messagebox.showinfo("Unit Optimized", f"Power play unit {unit_num} optimized for offensive production!")
        else:
            tk.messagebox.showwarning("Insufficient Players", f"Not enough available players to optimize PP{unit_num}.")

    def _optimize_penalty_kill_unit(self, unit_num):
        """Optimize a penalty kill unit"""
        self._save_undo_state()
        
        # Get best defensive players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        defensemen = [p for p in self.roster if p.primary_position.value in ['LD', 'RD', 'D']]
        
        # Sort by defensive skills
        forwards.sort(key=lambda p: getattr(p, 'checking', 10) + getattr(p, 'defense', 10) + getattr(p, 'speed', 10), reverse=True)
        defensemen.sort(key=lambda p: getattr(p, 'defense', 10) + getattr(p, 'checking', 10) + getattr(p, 'hockey_iq', 10), reverse=True)
        
        unit_key = f'PK{unit_num}'
        
        # Skip players used in higher units
        used_forwards = []
        used_defense = []
        
        for i in range(1, unit_num):
            other_unit = f'PK{i}'
            if other_unit in self.lineup:
                used_forwards.extend([p for p in self.lineup[other_unit]['Forwards'] if p])
                used_defense.extend([p for p in self.lineup[other_unit]['Defense'] if p])
        
        # Get available players
        available_forwards = [p for p in forwards if p not in used_forwards]
        available_defense = [p for p in defensemen if p not in used_defense]
        
        # Assign best available players (PK uses 2 forwards, 2 defense)
        if len(available_forwards) >= 2 and len(available_defense) >= 2:
            self.lineup[unit_key]['Forwards'] = available_forwards[:2]
            self.lineup[unit_key]['Defense'] = available_defense[:2]
            self._mark_changes()
            self._update_analytics_display()
            tk.messagebox.showinfo("Unit Optimized", f"Penalty kill unit {unit_num} optimized for defensive strength!")
        else:
            tk.messagebox.showwarning("Insufficient Players", f"Not enough available players to optimize PK{unit_num}.")

    def _create_enhanced_player_icons(self):
        """Create enhanced player icons based on quality tiers - placeholder"""
        # For now, return empty dict - will be enhanced in future stages
        return {}

    def _assess_player_quality(self, player):
        """Assess player quality tier (Elite, Star, Solid, Average, Depth) - placeholder"""
        if not player:
            return "Average"
        
        # Simple assessment based on overall rating
        overall = getattr(player, 'overall', 75)
        if overall >= 90:
            return "Elite"
        elif overall >= 85:
            return "Star"
        elif overall >= 80:
            return "Solid"
        elif overall >= 75:
            return "Average"
        else:
            return "Depth"

    def _calculate_chemistry_factors(self, players):
        """Calculate chemistry factors for a group of players - placeholder"""
        # For now, return neutral chemistry
        return {"overall": 50, "factors": []}

    def _setup_auto_save(self):
        """Setup auto-save functionality - placeholder"""
        # For now, just track changes
        self.changes_made = False
        self.last_save_time = None

    # Stage 2: Advanced functionality methods
    def undo_action(self):
        """Undo last action"""
        if hasattr(self, 'undo_stack') and self.undo_stack:
            current_state = self._get_lineup_state()
            if not hasattr(self, 'redo_stack'):
                self.redo_stack = []
            self.redo_stack.append(current_state)
            previous_state = self.undo_stack.pop()
            self._restore_lineup_state(previous_state)
            self._mark_changes()
            if hasattr(self, '_update_analytics_display'):
                self._update_analytics_display()

    def redo_action(self):
        """Redo last undone action"""
        if hasattr(self, 'redo_stack') and self.redo_stack:
            current_state = self._get_lineup_state()
            if not hasattr(self, 'undo_stack'):
                self.undo_stack = []
            self.undo_stack.append(current_state)
            next_state = self.redo_stack.pop()
            self._restore_lineup_state(next_state)
            self._mark_changes()
            if hasattr(self, '_update_analytics_display'):
                self._update_analytics_display()

    def shuffle_lines(self):
        """Intelligently shuffle lines based on chemistry"""
        import random
        
        # Save current state for undo
        self._save_undo_state()
        
        # Get available players
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        defense = [p for p in self.roster if p.primary_position.value in ['LD', 'RD', 'D']]
        
        # Shuffle with some intelligence (keep good players on higher lines)
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        defense.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Add some randomness while maintaining general quality order
        for i in range(len(forwards) - 1):
            if random.random() < 0.3:  # 30% chance to swap adjacent players
                if i + 1 < len(forwards):
                    forwards[i], forwards[i + 1] = forwards[i + 1], forwards[i]
        
        # Update forward lines
        forward_index = 0
        for line in range(4):
            for pos in range(3):
                if forward_index < len(forwards):
                    self.lineup['Forwards'][line][pos] = forwards[forward_index]
                    forward_index += 1
        
        # Update defense pairs
        defense_index = 0
        for pair in range(3):
            for pos in range(2):
                if defense_index < len(defense):
                    self.lineup['Defense'][pair][pos] = defense[defense_index]
                    defense_index += 1
        
        self._mark_changes()
        if hasattr(self, '_update_analytics_display'):
            self._update_analytics_display()
        tk.messagebox.showinfo("Success", "Lines shuffled with intelligent chemistry consideration!")

    def export_lines(self):
        """Export current lineup to file"""
        try:
            from tkinter import filedialog
            import json
            import datetime
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Lineup"
            )
            
            if filename:
                export_data = {
                    'lineup': self.lineup,
                    'team_name': self.parent.user_team.name,
                    'export_date': str(datetime.datetime.now()),
                    'version': '2.0'
                }
                
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                tk.messagebox.showinfo("Success", f"Lineup exported to {filename}")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to export lineup: {e}")

    def toggle_auto_save(self):
        """Toggle auto-save functionality"""
        if hasattr(self, 'auto_save_var'):
            self.auto_save_enabled = self.auto_save_var.get()
            if self.auto_save_enabled and hasattr(self, 'changes_made') and self.changes_made:
                self.save_lines(silent=True)

    def show_full_analysis(self):
        """Show comprehensive lineup analysis"""
        analysis_window = tk.Toplevel(self)
        analysis_window.title("🏒 Complete Lineup Analysis")
        analysis_window.geometry("800x600")
        analysis_window.configure(background=self.parent.BG_COLOR)
        
        # Create scrollable text widget for analysis
        text_frame = ttk.Frame(analysis_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        analysis_text = tk.Text(text_frame, wrap=tk.WORD, 
                               background=self.parent.CONTENT_BG,
                               foreground=self.parent.TEXT_COLOR,
                               font=(self.parent.FONT_FAMILY, 10))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=analysis_text.yview)
        analysis_text.configure(yscrollcommand=scrollbar.set)
        
        analysis_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Generate comprehensive analysis
        analysis = self._generate_full_analysis()
        analysis_text.insert(tk.END, analysis)
        analysis_text.configure(state="disabled")

    def _save_undo_state(self):
        """Save current state to undo stack"""
        if not hasattr(self, 'undo_stack'):
            self.undo_stack = []
        if not hasattr(self, 'redo_stack'):
            self.redo_stack = []
            
        current_state = self._get_lineup_state()
        self.undo_stack.append(current_state)
        # Limit undo stack size
        if len(self.undo_stack) > 10:
            self.undo_stack.pop(0)
        # Clear redo stack when new action is performed
        self.redo_stack.clear()

    def _get_lineup_state(self):
        """Get current lineup state for undo/redo"""
        import copy
        return copy.deepcopy(self.lineup)

    def _restore_lineup_state(self, state):
        """Restore lineup from saved state"""
        self.lineup = state
        # Update UI elements here if needed

    def _mark_changes(self):
        """Mark that changes have been made"""
        self.changes_made = True
        if hasattr(self, 'changes_label'):
            self.changes_label.config(text="● Unsaved changes")
        
        if hasattr(self, 'auto_save_enabled') and self.auto_save_enabled:
            # Disabled auto-save for stability
            pass
            # self.after(1000, lambda: self.save_lines(silent=True))

    def _update_analytics_display(self):
        """Update the analytics display panel"""
        if not hasattr(self, 'analytics_content'):
            return
            
        # Clear existing analytics
        for widget in self.analytics_content.winfo_children():
            widget.destroy()
        
        # Calculate current lineup analytics
        analytics = self._calculate_lineup_analytics()
        
        # Display analytics
        row = 0
        for category, value in analytics.items():
            ttk.Label(self.analytics_content, text=f"{category}:", 
                     style='Heading.TLabel').grid(row=row, column=0, sticky="w", padx=5)
            ttk.Label(self.analytics_content, text=str(value),
                     style='TLabel').grid(row=row, column=1, sticky="w", padx=5)
            row += 1

    def _calculate_lineup_analytics(self):
        """Calculate comprehensive lineup analytics"""
        analytics = {}
        
        # Calculate average ratings by line
        for i, line in enumerate(self.lineup['Forwards']):
            players = [p for p in line if p]
            if players:
                avg_rating = sum(p.overall_rating() for p in players) / len(players)
                analytics[f"Line {i+1} Avg"] = f"{avg_rating:.1f}"
        
        # Calculate defense pair ratings
        for i, pair in enumerate(self.lineup['Defense']):
            players = [p for p in pair if p]
            if players:
                avg_rating = sum(p.overall_rating() for p in players) / len(players)
                analytics[f"D-Pair {i+1} Avg"] = f"{avg_rating:.1f}"
        
        # Goalie ratings
        goalies = [g for g in self.lineup['Goalies'] if g]
        if goalies:
            analytics["Starter Rating"] = f"{goalies[0].overall_rating():.1f}"
            if len(goalies) > 1:
                analytics["Backup Rating"] = f"{goalies[1].overall_rating():.1f}"
        
        return analytics

    def _update_suggestions_display(self):
        """Update the suggestions display panel"""
        if not hasattr(self, 'suggestions_frame'):
            return
            
        # Clear existing suggestions
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()
        
        suggestions = self._generate_smart_suggestions()
        
        row = 0
        for suggestion in suggestions[:5]:  # Show top 5 suggestions
            suggestion_btn = ttk.Button(self.suggestions_frame,
                                       text=suggestion['text'],
                                       style='Secondary.TButton',
                                       command=lambda s=suggestion: self._apply_suggestion(s))
            suggestion_btn.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
            row += 1

    def _generate_smart_suggestions(self):
        """Generate AI-powered lineup suggestions"""
        suggestions = []
        
        # Example suggestions (would be more sophisticated in full implementation)
        suggestions.append({
            'text': "Move best scorer to top line",
            'action': 'optimize_top_line'
        })
        suggestions.append({
            'text': "Balance defensive pairs",
            'action': 'balance_defense'
        })
        suggestions.append({
            'text': "Optimize power play chemistry",
            'action': 'optimize_powerplay'
        })
        suggestions.append({
            'text': "Balance ice time distribution",
            'action': 'balance_ice_time'
        })
        
        return suggestions

    def _apply_suggestion(self, suggestion):
        """Apply a smart suggestion"""
        self._save_undo_state()
        
        if suggestion['action'] == 'optimize_top_line':
            self._optimize_top_line()
        elif suggestion['action'] == 'balance_defense':
            self._balance_defense_pairs()
        # Add more suggestion implementations
        
        self._mark_changes()
        self._update_analytics_display()

    def _optimize_top_line(self):
        """Optimize the top line with best players"""
        forwards = [p for p in self.roster if p.primary_position.value in ['C', 'LW', 'RW']]
        forwards.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        if len(forwards) >= 3:
            self.lineup['Forwards'][0] = forwards[:3]

    def _balance_defense_pairs(self):
        """Balance defensive pairs by skill"""
        defense = [p for p in self.roster if p.primary_position.value in ['LD', 'RD', 'D']]
        defense.sort(key=lambda p: p.overall_rating(), reverse=True)
        
        # Pair strong with weaker players for balance
        if len(defense) >= 6:
            self.lineup['Defense'][0] = [defense[0], defense[3]]
            self.lineup['Defense'][1] = [defense[1], defense[4]]
            self.lineup['Defense'][2] = [defense[2], defense[5]]

    def _generate_full_analysis(self):
        """Generate comprehensive text analysis"""
        analysis = "🏒 COMPLETE LINEUP ANALYSIS\n"
        analysis += "=" * 50 + "\n\n"
        
        # Forward lines analysis
        analysis += "FORWARD LINES:\n"
        for i, line in enumerate(self.lineup['Forwards']):
            players = [p for p in line if p]
            if players:
                avg_rating = sum(p.overall_rating() for p in players) / len(players)
                analysis += f"Line {i+1}: {avg_rating:.1f} avg\n"
                for j, player in enumerate(players):
                    analysis += f"  {['LW', 'C', 'RW'][j]}: {player.full_name} ({player.overall_rating():.1f})\n"
                analysis += "\n"
        
        # Defense pairs analysis
        analysis += "DEFENSE PAIRS:\n"
        for i, pair in enumerate(self.lineup['Defense']):
            players = [p for p in pair if p]
            if players:
                avg_rating = sum(p.overall_rating() for p in players) / len(players)
                analysis += f"Pair {i+1}: {avg_rating:.1f} avg\n"
                for j, player in enumerate(players):
                    analysis += f"  {['LD', 'RD'][j]}: {player.full_name} ({player.overall_rating():.1f})\n"
                analysis += "\n"
        
        # Goalies analysis
        analysis += "GOALIES:\n"
        for i, goalie in enumerate(self.lineup['Goalies']):
            if goalie:
                role = "Starter" if i == 0 else "Backup"
                analysis += f"{role}: {goalie.full_name} ({goalie.overall_rating():.1f})\n"
        
        return analysis

    # Stage 3: Enhanced interface builders (using existing functionality for now)
    # ------------------------------------------------------------------
    def _ui_color(self, key, default):
        """Theme color with safe fallback (parent may not expose a COLORS dict)."""
        colors = getattr(self.parent, 'COLORS', None)
        if isinstance(colors, dict):
            return colors.get(key, default)
        return {'bg': getattr(self.parent, 'BG_COLOR', '#1a1d24'),
                'card': getattr(self.parent, 'CARD_COLOR', '#242832')}.get(key, default)

    # Chemistry tab: every line's score plus exactly what helps / hurts it.
    # ------------------------------------------------------------------
    def _build_chemistry_tab(self):
        """Build the Chemistry tab: per-line scores with +/- factor breakdowns."""
        for child in self.chem_frame.winfo_children():
            child.destroy()
        wrap = ttk.Frame(self.chem_frame, style='Panel.TFrame')
        wrap.pack(fill="both", expand=True, padx=12, pady=10)

        header = ttk.Frame(wrap, style='Panel.TFrame')
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Line Chemistry",
                  font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  style='Heading.TLabel').pack(side="left")
        ttk.Label(header, text="What makes each unit click - and what drags it down",
                  style='Secondary.TLabel').pack(side="left", padx=(12, 0))
        ttk.Button(header, text="Refresh",
                   command=self._build_chemistry_tab).pack(side="right")

        # Scrollable content
        canvas = tk.Canvas(wrap, highlightthickness=0,
                           background=self._ui_color('bg', '#1a1d24'))
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style='Panel.TFrame')
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        units = []
        for i in range(4):
            det = self.calculate_line_chemistry_detailed(self.lineup['Forwards'][i])
            if det:
                names = " - ".join(p.full_name for p in self.lineup['Forwards'][i])
                units.append((f"Forward Line {i+1}", names, det))
        for i in range(3):
            det = self.calculate_defense_chemistry_detailed(self.lineup['Defense'][i])
            if det:
                names = " - ".join(p.full_name for p in self.lineup['Defense'][i])
                units.append((f"Defense Pair {i+1}", names, det))

        if not units:
            ttk.Label(body, text="Set your lines first - chemistry appears once a unit is complete.",
                      style='Secondary.TLabel').pack(pady=30)
            return

        avg = sum(u[2][0] for u in units) / len(units)
        self._chem_card(body, "Team Average", f"{len(units)} units dressed",
                        (round(avg), self._chemistry_rating(round(avg)),
                         [(0, "Overall blend", "Average across all forward lines and defense pairs")]),
                        summary=True)

        for title, names, det in units:
            self._chem_card(body, title, names, det)

    def _chem_card(self, parent, title, subtitle, det, summary=False):
        """One unit's chemistry card: score bar, rating, and +/- factor rows."""
        score, rating, factors = det
        color = self._get_chemistry_color(rating)
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.pack(fill="x", pady=6)

        top = ttk.Frame(card, style='Card.TFrame')
        top.pack(fill="x")
        ttk.Label(top, text=title, font=(self.parent.FONT_FAMILY, 12, 'bold'),
                  style='Card.TLabel').pack(side="left")
        ttk.Label(top, text=f"  {score}", font=(self.parent.FONT_FAMILY, 16, 'bold'),
                  foreground=color, background=self._ui_color('card', '#242832')).pack(side="left")
        ttk.Label(top, text=f"  {rating}", font=(self.parent.FONT_FAMILY, 11, 'bold'),
                  foreground=color, background=self._ui_color('card', '#242832')).pack(side="left")
        ttk.Label(top, text=subtitle, style='Secondary.TLabel').pack(side="left", padx=(10, 0))

        # Score bar
        bar = tk.Canvas(card, height=8, highlightthickness=0,
                        background=self._ui_color('bg', '#1a1d24'))
        bar.pack(fill="x", pady=(8, 4))
        bar.update_idletasks()
        w = bar.winfo_width() or 400
        bar.create_rectangle(0, 0, w, 8, fill="#3a3f4b", outline="")
        bar.create_rectangle(0, 0, w * score / 100, 8, fill=color, outline="")

        if summary:
            return

        pos = [f for f in factors if f[0] > 0]
        neg = [f for f in factors if f[0] < 0]
        neut = [f for f in factors if f[0] == 0]

        cols = ttk.Frame(card, style='Card.TFrame')
        cols.pack(fill="x", pady=(4, 0))
        left = ttk.Frame(cols, style='Card.TFrame')
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.Frame(cols, style='Card.TFrame')
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Helping", font=(self.parent.FONT_FAMILY, 10, 'bold'),
                  foreground="#27ae60",
                  background=self._ui_color('card', '#242832')).pack(anchor="w", pady=(0, 2))
        if pos:
            for d, t, detl in sorted(pos, key=lambda f: -f[0]):
                self._chem_factor_row(left, d, t, detl, "#27ae60")
        else:
            ttk.Label(left, text="Nothing working for this unit yet.",
                      style='Secondary.TLabel').pack(anchor="w")

        ttk.Label(right, text="Hurting", font=(self.parent.FONT_FAMILY, 10, 'bold'),
                  foreground="#e74c3c",
                  background=self._ui_color('card', '#242832')).pack(anchor="w", pady=(0, 2))
        if neg:
            for d, t, detl in sorted(neg, key=lambda f: f[0]):
                self._chem_factor_row(right, d, t, detl, "#e74c3c")
        else:
            ttk.Label(right, text="No drag factors - clean unit.",
                      style='Secondary.TLabel').pack(anchor="w")

        for d, t, detl in neut:
            row = ttk.Frame(card, style='Card.TFrame')
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"· {t}: {detl}", style='Secondary.TLabel',
                      wraplength=520, justify="left").pack(anchor="w")

    def _chem_factor_row(self, parent, delta, title, detail, color):
        row = ttk.Frame(parent, style='Card.TFrame')
        row.pack(fill="x", pady=2)
        sign = "+" if delta > 0 else ""
        ttk.Label(row, text=f"{sign}{delta}", font=(self.parent.FONT_FAMILY, 10, 'bold'),
                  foreground=color, width=5,
                  background=self._ui_color('card', '#242832')).pack(side="left")
        txt = ttk.Frame(row, style='Card.TFrame')
        txt.pack(side="left", fill="x", expand=True)
        ttk.Label(txt, text=title, font=(self.parent.FONT_FAMILY, 10, 'bold'),
                  background=self._ui_color('card', '#242832')).pack(anchor="w")
        ttk.Label(txt, text=detail, style='Secondary.TLabel',
                  wraplength=300, justify="left").pack(anchor="w")

    def _on_lines_tab_changed(self, event=None):
        """Refresh the Chemistry tab whenever it is opened so it tracks edits."""
        try:
            if self.notebook.tab(self.notebook.select(), "text") == "Chemistry":
                self._build_chemistry_tab()
        except Exception:
            pass

    def _build_enhanced_even_strength_tab(self):
        """Build enhanced even strength tab - Stage 3 with fallback"""
        try:
            # Try to use existing functionality, but handle gracefully if not ready
            if hasattr(self, '_build_even_strength_editor'):
                self._build_even_strength_editor()
        except (AttributeError, IndexError) as e:
            # Fallback: Create basic interface
            self._create_basic_even_strength_tab()

    def _build_enhanced_power_play_tab(self):
        """Build enhanced power play tab - Stage 3 with fallback"""
        try:
            if hasattr(self, '_build_power_play_editor'):
                self._build_power_play_editor()
        except (AttributeError, IndexError) as e:
            self._create_basic_power_play_tab()

    def _build_enhanced_penalty_kill_tab(self):
        """Build enhanced penalty kill tab - Stage 3 with fallback"""
        try:
            if hasattr(self, '_build_penalty_kill_editor'):
                self._build_penalty_kill_editor()
        except (AttributeError, IndexError) as e:
            self._create_basic_penalty_kill_tab()

    def _build_enhanced_goalie_tab(self):
        """Build enhanced goalie tab - Stage 3 with fallback"""
        try:
            if hasattr(self, '_build_goalie_editor'):
                self._build_goalie_editor()
        except (AttributeError, IndexError) as e:
            self._create_basic_goalie_tab()

    def _build_enhanced_strategy_tab(self):
        """Build enhanced strategy tab - Stage 3 with fallback"""
        try:
            if hasattr(self, '_build_strategy_editor'):
                self._build_strategy_editor()
        except (AttributeError, IndexError) as e:
            self._create_basic_strategy_tab()

    def _create_basic_even_strength_tab(self):
        """Create basic even strength tab as fallback"""
        ttk.Label(self.even_frame, text="Even Strength Lines", 
                 style='Title.TLabel').pack(pady=10)
        ttk.Label(self.even_frame, text="Enhanced interface coming soon...", 
                 style='TLabel').pack(pady=20)

    def _create_basic_power_play_tab(self):
        """Create basic power play tab as fallback"""
        ttk.Label(self.pp_frame, text="Power Play Lines", 
                 style='Title.TLabel').pack(pady=10)
        ttk.Label(self.pp_frame, text="Enhanced interface coming soon...", 
                 style='TLabel').pack(pady=20)

    def _create_basic_penalty_kill_tab(self):
        """Create basic penalty kill tab as fallback"""
        ttk.Label(self.pk_frame, text="Penalty Kill Lines", 
                 style='Title.TLabel').pack(pady=10)
        ttk.Label(self.pk_frame, text="Enhanced interface coming soon...", 
                 style='TLabel').pack(pady=20)

    def _create_basic_goalie_tab(self):
        """Create basic goalie tab as fallback"""
        ttk.Label(self.g_frame, text="Goalie Settings", 
                 style='Title.TLabel').pack(pady=10)
        ttk.Label(self.g_frame, text="Enhanced interface coming soon...", 
                 style='TLabel').pack(pady=20)

    def _create_basic_strategy_tab(self):
        """Create basic strategy tab as fallback"""
        ttk.Label(self.strat_frame, text="Team Strategies", 
                 style='Title.TLabel').pack(pady=10)
        ttk.Label(self.strat_frame, text="Enhanced interface coming soon...", 
                 style='TLabel').pack(pady=20)

    def _build_real_time_analytics_tab(self):
        """Build real-time analytics tab"""
        # Create analytics tab content
        analytics_main = ttk.Frame(self.analytics_frame, style='Panel.TFrame')
        analytics_main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(analytics_main, text="📊 Real-Time Lineup Analytics", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Analytics content will be updated in real-time
        self.analytics_content_tab = ttk.Frame(analytics_main, style='Panel.TFrame')
        self.analytics_content_tab.pack(fill="both", expand=True)
        
        # Initial analytics display
        self._display_analytics_tab_content()

    def _display_analytics_tab_content(self):
        """Display content in the analytics tab"""
        # Clear existing content
        for widget in self.analytics_content_tab.winfo_children():
            widget.destroy()
        
        # Team overview
        overview_frame = ttk.LabelFrame(self.analytics_content_tab, text="Team Overview", 
                                       style='Panel.TLabelframe')
        overview_frame.pack(fill="x", pady=(0, 10))
        
        # Calculate team statistics
        all_players = []
        for line in self.lineup['Forwards']:
            all_players.extend([p for p in line if p])
        for pair in self.lineup['Defense']:
            all_players.extend([p for p in pair if p])
        all_players.extend([g for g in self.lineup['Goalies'] if g])
        
        if all_players:
            avg_overall = sum(p.overall_rating() for p in all_players) / len(all_players)
            ttk.Label(overview_frame, text=f"Average Overall Rating: {avg_overall:.1f}",
                     style='TLabel').pack(anchor="w", padx=10, pady=5)
            ttk.Label(overview_frame, text=f"Total Players in Lineup: {len(all_players)}",
                     style='TLabel').pack(anchor="w", padx=10, pady=5)
        
        # Line chemistry analysis
        chemistry_frame = ttk.LabelFrame(self.analytics_content_tab, text="Line Chemistry", 
                                        style='Panel.TLabelframe')
        chemistry_frame.pack(fill="x", pady=(0, 10))
        
        for i, line in enumerate(self.lineup['Forwards']):
            players = [p for p in line if p]
            if players:
                chemistry_score = self._calculate_line_chemistry(players)
                chemistry_color = "green" if chemistry_score > 75 else "orange" if chemistry_score > 50 else "red"
                ttk.Label(chemistry_frame, 
                         text=f"Line {i+1} Chemistry: {chemistry_score:.1f}%",
                         style='TLabel').pack(anchor="w", padx=10, pady=2)

    def _calculate_line_chemistry(self, players):
        """Calculate chemistry between players on a line"""
        if len(players) < 2:
            return 0
        
        # Simple chemistry calculation based on overall ratings and attributes
        base_chemistry = 50
        
        # Chemistry bonus for similar skill levels
        ratings = [p.overall_rating() for p in players]
        avg_rating = sum(ratings) / len(ratings)
        rating_variance = sum((r - avg_rating) ** 2 for r in ratings) / len(ratings)
        
        # Lower variance = better chemistry
        chemistry_bonus = max(0, 30 - rating_variance)
        
        return min(100, base_chemistry + chemistry_bonus)

    # New method stubs that will be implemented in future stages
    def auto_optimize_lines(self):
        """Auto-optimize lines based on player ratings and chemistry"""
        self.set_best_lines()  # Use existing functionality for now

    def copy_lines(self):
        """Copy current lineup to clipboard"""
        try:
            import json
            lineup_json = json.dumps(self.lineup, indent=2, default=str)
            self.clipboard_clear()
            self.clipboard_append(lineup_json)
            tk.messagebox.showinfo("Success", "Lineup copied to clipboard!")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to copy lineup: {e}")

    def import_lines(self):
        """Import lineup from clipboard or file"""
        try:
            import json
            clipboard_data = self.clipboard_get()
            imported_lineup = json.loads(clipboard_data)
            
            # Basic validation
            if isinstance(imported_lineup, dict) and 'Forwards' in imported_lineup:
                response = tk.messagebox.askyesno("Import Lineup", 
                    "Import lineup from clipboard? This will overwrite current lineup.")
                if response:
                    self.lineup = imported_lineup
                    tk.messagebox.showinfo("Success", "Lineup imported successfully!")
            else:
                tk.messagebox.showerror("Error", "Invalid lineup format in clipboard")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to import lineup: {e}")

    def save_lines(self, silent=False):
        """Enhanced save with optional silent mode"""
        # Update lineup from current selections
        # Forward lines
        for i in range(4):
            for j in range(3):
                name = self.fw_vars[i][j].get().split(' (')[0] if self.fw_vars[i][j].get() else ""
                self.lineup['Forwards'][i][j] = next(
                    (p for p in self.roster if p.full_name == name), None)

        # Defense pairs
        for i in range(4):
            for j in range(2):
                name = self.df_vars[i][j].get().split(' (')[0] if self.df_vars[i][j].get() else ""
                self.lineup['Defense'][i][j] = next(
                    (p for p in self.roster if p.full_name == name), None)

        # Goalies
        for i in range(2):
            name = self.g_vars[i].get().split(' (')[0] if self.g_vars[i].get() else ""
            self.lineup['Goalies'][i] = next(
                (p for p in self.roster if p.full_name == name), None)

        # Power Play
        for i in range(3):
            name = self.pp1_fw_vars[i].get().split(' (')[0] if self.pp1_fw_vars[i].get() else ""
            self.lineup['PP1']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pp2_fw_vars[i].get().split(' (')[0] if self.pp2_fw_vars[i].get() else ""
            self.lineup['PP2']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)

        for i in range(2):
            name = self.pp1_df_vars[i].get().split(' (')[0] if self.pp1_df_vars[i].get() else ""
            self.lineup['PP1']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pp2_df_vars[i].get().split(' (')[0] if self.pp2_df_vars[i].get() else ""
            self.lineup['PP2']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)

        # Penalty Kill
        for i in range(2):
            name = self.pk1_fw_vars[i].get().split(' (')[0] if self.pk1_fw_vars[i].get() else ""
            self.lineup['PK1']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pk2_fw_vars[i].get().split(' (')[0] if self.pk2_fw_vars[i].get() else ""
            self.lineup['PK2']['Forwards'][i] = next(
                (p for p in self.roster if p.full_name == name), None)

        for i in range(2):
            name = self.pk1_df_vars[i].get().split(' (')[0] if self.pk1_df_vars[i].get() else ""
            self.lineup['PK1']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)
            
            name = self.pk2_df_vars[i].get().split(' (')[0] if self.pk2_df_vars[i].get() else ""
            self.lineup['PK2']['Defense'][i] = next(
                (p for p in self.roster if p.full_name == name), None)

        # Update strategies (if they exist)
        if hasattr(self, 'strat_vars'):
            strategy_keys = ['EvenStrength', 'PowerPlay', 'PenaltyKill', 'LeadingBy2+', 'TrailingBy2+']
            for i, var in enumerate(self.strat_vars):
                if i < len(strategy_keys) and var.get():
                    self.lineup['Strategies'][strategy_keys[i]] = var.get()

        # Mark as saved
        self.changes_made = False
        self.changes_label.config(text="")
        
        # Update last modified
        import datetime
        self.lineup['LastModified'] = datetime.datetime.now().isoformat()

        # Save the lineup to the team
        self.parent.user_team.lineup = self.lineup
        self.parent.update_all_views()
        
        if not silent:
            tk.messagebox.showinfo("Success", "Lines have been saved!")
            self.destroy()
