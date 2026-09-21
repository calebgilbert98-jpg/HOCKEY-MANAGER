# scouting_management_window_new.py
# Simplified and Improved Scouting Management System

import tkinter as tk
from tkinter import ttk, messagebox
import random
from game_classes import Player, PlayerPosition, Staff, StaffRole, ScoutingReport
from typing import List, Dict, Optional

class ScoutingManagementWindow(tk.Toplevel):
    """Simplified and improved scouting management system."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Scouting Management")
        self.geometry("1200x800")
        self.configure(background=parent.BG_COLOR)
        self.resizable(True, True)
        
        # Debounce mechanism for filters
        self.filter_update_job = None
        self.filter_delay = 500  # 500ms delay
        
        # Initialize data
        self.current_tab = "players"
        self.players_data = {}
        self.scouts_data = []
        
        # Load data
        self._load_player_data()
        self._load_scout_data()
        self._initialize_general_assignments()
        
        # Create UI
        self.create_interface()
        self.populate_current_tab()
        
        # Track window
        self.parent.open_windows['scouting'] = self
        self.focus_set()
    
    def on_filter_change(self, *args):
        """Handle filter changes with debouncing to prevent too many rapid updates."""
        # Cancel any pending update
        if self.filter_update_job is not None:
            self.after_cancel(self.filter_update_job)
        
        # Schedule a new update after delay
        self.filter_update_job = self.after(self.filter_delay, self._apply_filters_debounced)
    
    def _apply_filters_debounced(self):
        """Apply filters after debounce delay."""
        print("Applying filters (debounced)...")
        self.filter_update_job = None
        self.populate_current_tab()

    def _load_player_data(self):
        """Load all player data into organized structure."""
        try:
            # NHL Players (teams + free agents)
            nhl_players = []
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
                for team in self.parent.game_manager.league.teams:
                    nhl_players.extend(team.roster)
                    nhl_players.extend(team.ahl_roster)
                nhl_players.extend(self.parent.game_manager.free_agents)
            
            # International Players
            international_players = []
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'database_manager'):
                international_players = self.parent.game_manager.database_manager.get_international_players()
            
            # Prospects
            prospects = []
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'database_manager'):
                prospects = self.parent.game_manager.database_manager.get_prospects()
            
            self.players_data = {
                'nhl': nhl_players,
                'international': international_players,
                'prospects': prospects,
                'all': nhl_players + international_players + prospects
            }
            
            print(f"Loaded players: NHL={len(nhl_players)}, International={len(international_players)}, Prospects={len(prospects)}")
            
        except Exception as e:
            print(f"Error loading player data: {e}")
            self.players_data = {'nhl': [], 'international': [], 'prospects': [], 'all': []}
    
    def _load_scout_data(self):
        """Load scout data."""
        try:
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                # Method 1: Look for Scout in role name
                self.scouts_data = [staff for staff in self.parent.game_manager.user_team.staff 
                                  if 'Scout' in staff.role.value]
                
                # Method 2: If none found, check for scouting abilities
                if not self.scouts_data:
                    self.scouts_data = [staff for staff in self.parent.game_manager.user_team.staff 
                                      if hasattr(staff, 'judging_player_ability') and 
                                         hasattr(staff, 'judging_player_potential') and
                                         staff.judging_player_ability > 0]
                
                # Method 3: If still none, look for any staff that could scout (fallback)
                if not self.scouts_data:
                    # Get staff that are not coaches or management
                    non_coach_roles = [staff for staff in self.parent.game_manager.user_team.staff 
                                     if 'Coach' not in staff.role.value and 
                                        'Manager' not in staff.role.value and
                                        'Medical' not in staff.role.value]
                    self.scouts_data = non_coach_roles[:5]  # Take up to 5 staff as potential scouts
            
            print(f"Loaded {len(self.scouts_data)} scouts")
            if self.scouts_data:
                print(f"Scout roles: {[scout.role.value for scout in self.scouts_data]}")
            else:
                print("No scouts found. Available staff roles:")
                if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                    for staff in self.parent.game_manager.user_team.staff[:5]:  # Show first 5
                        print(f"  - {staff.full_name}: {staff.role.value}")
        except Exception as e:
            print(f"Error loading scout data: {e}")
            self.scouts_data = []
    
    def _initialize_general_assignments(self):
        """Initialize general scouting assignments if they don't exist."""
        try:
            if hasattr(self.parent, 'game_manager'):
                if not hasattr(self.parent.game_manager, 'general_scouting_assignments'):
                    self.parent.game_manager.general_scouting_assignments = []
                    
                    # Add some default assignments if starting fresh
                    if len(self.scouts_data) > 0:
                        default_assignments = [
                            {
                                'type': 'Draft',
                                'region_league': '2025 Draft Class',
                                'scout': self.scouts_data[0],
                                'scout_name': self.scouts_data[0].full_name,
                                'priority': 'High',
                                'status': 'Active',
                                'created_date': 'Game Start'
                            }
                        ]
                        
                        if len(self.scouts_data) > 1:
                            default_assignments.append({
                                'type': 'International',
                                'region_league': 'Scandinavian Europe',
                                'scout': self.scouts_data[1],
                                'scout_name': self.scouts_data[1].full_name,
                                'priority': 'Medium',
                                'status': 'Active',
                                'created_date': 'Game Start'
                            })
                        
                        self.parent.game_manager.general_scouting_assignments = default_assignments
        except Exception as e:
            print(f"Error initializing general assignments: {e}")
    
    def create_interface(self):
        """Create the main interface."""
        # Header
        header_frame = tk.Frame(self, bg=self.parent.TITLE_BAR_COLOR, height=50)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="SCOUTING MANAGEMENT", 
                font=(self.parent.FONT_FAMILY, 16, "bold"),
                bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=15)
        
        # Tab buttons
        tab_frame = tk.Frame(self, bg=self.parent.BG_COLOR)
        tab_frame.pack(fill='x', padx=20, pady=10)
        
        self.tab_buttons = {}
        tabs = [
            ("players", "PLAYERS", "Browse and scout players"),
            ("scouts", "SCOUTS", "Manage scout assignments"),
            ("management", "MANAGEMENT", "Scout management and general assignments"),
            ("reports", "REPORTS", "View scouting reports")
        ]
        
        for tab_id, text, tooltip in tabs:
            btn = tk.Button(tab_frame, text=text,
                           font=(self.parent.FONT_FAMILY, 10, "bold"),
                           bg=self.parent.ACCENT_COLOR if tab_id == self.current_tab else self.parent.CONTENT_BG,
                           fg=self.parent.HEADER_COLOR,
                           activebackground=self.parent.ACCENT_HOVER,
                           relief='flat', bd=0, padx=20, pady=5,
                           command=lambda t=tab_id: self.switch_tab(t))
            btn.pack(side='left', padx=(0, 5))
            self.tab_buttons[tab_id] = btn
        
        # Filters frame
        self.filters_frame = tk.Frame(self, bg=self.parent.CONTENT_BG)
        self.filters_frame.pack(fill='x', padx=20, pady=5)
        
        # Main content frame
        content_frame = tk.Frame(self, bg=self.parent.CONTENT_BG)
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Treeview with scrollbar
        tree_frame = tk.Frame(content_frame, bg=self.parent.CONTENT_BG)
        tree_frame.pack(fill='both', expand=True)
        
        # Create columns based on current tab
        self.setup_treeview(tree_frame)
        
        # Status bar
        self.status_bar = tk.Label(self, text="Ready", 
                                  font=(self.parent.FONT_FAMILY, 9),
                                  bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.TEXT_COLOR,
                                  anchor='w', padx=10)
        self.status_bar.pack(fill='x', side='bottom')
    
    def setup_treeview(self, parent_frame):
        """Setup the treeview widget."""
        # Define columns based on current tab
        if self.current_tab == "players":
            columns = ('Name', 'Position', 'Age', 'Team', 'Overall', 'Scouted')
            widths = (200, 80, 60, 150, 80, 80)
        elif self.current_tab == "scouts":
            columns = ('Scout', 'Role', 'Skill', 'Assigned Player', 'Progress')
            widths = (150, 120, 80, 200, 100)
        elif self.current_tab == "management":
            columns = ('Assignment Type', 'Assigned Scout', 'Region/League', 'Status', 'Priority')
            widths = (150, 150, 200, 100, 80)
        else:  # reports
            columns = ('Player', 'Scout', 'Accuracy', 'Viewings', 'Last Update')
            widths = (200, 150, 80, 80, 100)
        
        # Create treeview
        self.tree = ttk.Treeview(parent_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        for i, (col, width) in enumerate(zip(columns, widths)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, minwidth=50)
        
        # Add scrollbars
        v_scroll = ttk.Scrollbar(parent_frame, orient='vertical', command=self.tree.yview)
        h_scroll = ttk.Scrollbar(parent_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Pack widgets
        self.tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')
        
        # Bind events
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<Button-3>', self.on_right_click)
        
        # Context menu
        self.create_context_menu()
    
    def create_context_menu(self):
        """Create context menu for current tab."""
        self.context_menu = tk.Menu(self, tearoff=0)
        
        if self.current_tab == "players":
            self.context_menu.add_command(label="Scout Player", command=self.scout_player)
            self.context_menu.add_command(label="View Profile", command=self.view_player_profile)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Add to Watchlist", command=self.add_to_watchlist)
        elif self.current_tab == "scouts":
            self.context_menu.add_command(label="Assign Scout", command=self.assign_scout)
            self.context_menu.add_command(label="Remove Assignment", command=self.remove_assignment)
        elif self.current_tab == "management":
            self.context_menu.add_command(label="Create Assignment", command=self.create_general_assignment)
            self.context_menu.add_command(label="Modify Assignment", command=self.modify_assignment)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Remove Assignment", command=self.remove_general_assignment)
        else:  # reports
            self.context_menu.add_command(label="View Report", command=self.view_report)
            self.context_menu.add_command(label="Delete Report", command=self.delete_report)
    
    def create_filters(self):
        """Create filter widgets for current tab."""
        # Clear existing filters
        for widget in self.filters_frame.winfo_children():
            widget.destroy()
        
        if self.current_tab == "players":
            # Player category filter
            tk.Label(self.filters_frame, text="Category:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 5))
            
            self.category_var = tk.StringVar(value="all")
            category_combo = ttk.Combobox(self.filters_frame, textvariable=self.category_var, 
                                        width=12, values=["all", "nhl", "international", "prospects"])
            category_combo.pack(side='left', padx=(0, 20))
            category_combo.bind('<<ComboboxSelected>>', lambda e: self.populate_current_tab())
            self.category_var.trace('w', self.on_filter_change)
            
            # Position filter
            tk.Label(self.filters_frame, text="Position:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 5))
            
            self.position_var = tk.StringVar(value="All")
            position_combo = ttk.Combobox(self.filters_frame, textvariable=self.position_var, 
                                        width=10, values=["All", "C", "LW", "RW", "LD", "RD", "D", "G"])
            position_combo.pack(side='left', padx=(0, 20))
            position_combo.bind('<<ComboboxSelected>>', lambda e: self.populate_current_tab())
            self.position_var.trace('w', self.on_filter_change)
            
            # Name search
            tk.Label(self.filters_frame, text="Search:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 5))
            
            self.search_var = tk.StringVar()
            search_entry = tk.Entry(self.filters_frame, textvariable=self.search_var, width=20)
            search_entry.pack(side='left', padx=(0, 20))
            search_entry.bind('<KeyRelease>', lambda e: self.populate_current_tab())
            
            # Overall rating filter
            tk.Label(self.filters_frame, text="Min Overall:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 5))
            
            self.overall_var = tk.StringVar(value="0")
            overall_spin = tk.Spinbox(self.filters_frame, textvariable=self.overall_var, 
                                    from_=0, to=100, width=5, command=self.populate_current_tab)
            overall_spin.pack(side='left', padx=(0, 20))
            # Also bind to value changes in the spinbox
            self.overall_var.trace('w', self.on_filter_change)
            
            # Clear button
            tk.Button(self.filters_frame, text="Clear Filters", 
                     bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                     command=self.clear_filters).pack(side='left', padx=10)
        
        elif self.current_tab == "management":
            # Management controls
            tk.Label(self.filters_frame, text="Scout Management:", 
                    font=(self.parent.FONT_FAMILY, 10, "bold"),
                    bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 20))
            
            # Create new assignment button
            tk.Button(self.filters_frame, text="Create Assignment", 
                     bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                     command=self.create_general_assignment).pack(side='left', padx=(0, 10))
            
            # Assignment type filter
            tk.Label(self.filters_frame, text="Type:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(10, 5))
            
            self.assignment_type_var = tk.StringVar(value="All")
            type_combo = ttk.Combobox(self.filters_frame, textvariable=self.assignment_type_var, 
                                    width=15, values=["All", "Regional", "League", "Youth", "Draft", "International"])
            type_combo.pack(side='left', padx=(0, 20))
            type_combo.bind('<<ComboboxSelected>>', lambda e: self.populate_current_tab())
    
    def switch_tab(self, tab_id):
        """Switch to a different tab."""
        self.current_tab = tab_id
        
        # Update button appearances
        for tid, btn in self.tab_buttons.items():
            if tid == tab_id:
                btn.configure(bg=self.parent.ACCENT_COLOR)
            else:
                btn.configure(bg=self.parent.CONTENT_BG)
        
        # Recreate interface elements
        self.create_filters()
        
        # Recreate treeview
        for widget in self.tree.master.winfo_children():
            if isinstance(widget, ttk.Treeview):
                widget.destroy()
            elif isinstance(widget, ttk.Scrollbar):
                widget.destroy()
        
        self.setup_treeview(self.tree.master)
        self.populate_current_tab()
    
    def populate_current_tab(self):
        """Populate the current tab with data."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            if self.current_tab == "players":
                self.populate_players()
            elif self.current_tab == "scouts":
                self.populate_scouts()
            elif self.current_tab == "management":
                self.populate_management()
            else:  # reports
                self.populate_reports()
        except Exception as e:
            print(f"Error populating tab {self.current_tab}: {e}")
            self.status_bar.configure(text=f"Error loading data: {e}")
    
    def populate_players(self):
        """Populate players tab."""
        # Get filter values
        category = getattr(self, 'category_var', tk.StringVar(value="all")).get()
        position_filter = getattr(self, 'position_var', tk.StringVar(value="All")).get()
        search_term = getattr(self, 'search_var', tk.StringVar()).get().lower()
        min_overall = int(getattr(self, 'overall_var', tk.StringVar(value="0")).get() or 0)
        
        # Get players based on category
        if category == "all":
            players = self.players_data.get('all', [])
        else:
            players = self.players_data.get(category, [])
        
        filtered_players = []
        for player in players:
            try:
                # Apply filters
                if position_filter != "All" and player.primary_position.name != position_filter:
                    continue
                
                if search_term and search_term not in player.full_name.lower():
                    continue
                
                overall = player.overall_rating()
                if overall < min_overall:
                    continue
                
                # Check if scouted
                scouted = "No"
                if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                    if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                        scouted = "Yes" if player.id in self.parent.game_manager.user_team.scouting_reports else "No"
                
                # Add to tree
                self.tree.insert('', 'end', values=(
                    player.full_name,
                    player.primary_position.name,
                    player.age,
                    player.team_name,
                    overall,
                    scouted
                ))
                filtered_players.append(player)
                
            except Exception as e:
                print(f"Error processing player {getattr(player, 'full_name', 'Unknown')}: {e}")
                continue
        
        self.status_bar.configure(text=f"Showing {len(filtered_players)} players")
    
    def populate_scouts(self):
        """Populate scouts tab."""
        for scout in self.scouts_data:
            try:
                skill = (scout.judging_player_ability + scout.judging_player_potential) / 2
                
                # Check assignments
                assigned_player = "None"
                progress = "N/A"
                
                if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'scouting_assignments'):
                    for player, assigned_scout in self.parent.game_manager.scouting_assignments.items():
                        if assigned_scout.id == scout.id:
                            assigned_player = player.full_name
                            # Get progress from reports
                            if hasattr(self.parent.game_manager, 'user_team'):
                                if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                                    report = self.parent.game_manager.user_team.scouting_reports.get(player.id)
                                    if report:
                                        progress = f"{report.viewings}/15"
                            break
                
                self.tree.insert('', 'end', values=(
                    scout.full_name,
                    scout.role.value,
                    f"{skill:.0f}",
                    assigned_player,
                    progress
                ))
                
            except Exception as e:
                print(f"Error processing scout {getattr(scout, 'full_name', 'Unknown')}: {e}")
                continue
        
        self.status_bar.configure(text=f"Showing {len(self.scouts_data)} scouts")
    
    def populate_reports(self):
        """Populate reports tab."""
        try:
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                    reports = self.parent.game_manager.user_team.scouting_reports
                    
                    for player_id, report in reports.items():
                        try:
                            last_update = "Never"
                            if report.last_viewed:
                                last_update = report.last_viewed.strftime("%m/%d/%Y")
                            
                            self.tree.insert('', 'end', values=(
                                report.player.full_name,
                                report.scout.full_name,
                                report.accuracy,
                                report.viewings,
                                last_update
                            ))
                        except Exception as e:
                            print(f"Error processing report: {e}")
                            continue
                    
                    self.status_bar.configure(text=f"Showing {len(reports)} reports")
                else:
                    self.status_bar.configure(text="No scouting reports available")
            else:
                self.status_bar.configure(text="Game manager not available")
        except Exception as e:
            print(f"Error loading reports: {e}")
            self.status_bar.configure(text=f"Error loading reports: {e}")
    
    def populate_management(self):
        """Populate management tab with general scouting assignments."""
        try:
            # Get general assignments from game manager
            general_assignments = self._get_general_assignments()
            
            # Filter by assignment type if specified
            assignment_type_filter = getattr(self, 'assignment_type_var', tk.StringVar(value="All")).get()
            
            filtered_assignments = []
            for assignment in general_assignments:
                if assignment_type_filter == "All" or assignment['type'] == assignment_type_filter:
                    filtered_assignments.append(assignment)
            
            # Populate tree
            for assignment in filtered_assignments:
                self.tree.insert('', 'end', values=(
                    assignment['type'],
                    assignment['scout_name'],
                    assignment['region_league'],
                    assignment['status'],
                    assignment['priority']
                ))
            
            self.status_bar.configure(text=f"Showing {len(filtered_assignments)} general assignments")
            
        except Exception as e:
            print(f"Error loading management data: {e}")
            self.status_bar.configure(text=f"Error loading management data: {e}")
    
    def clear_filters(self):
        """Clear all filters."""
        if hasattr(self, 'category_var'):
            self.category_var.set("all")
        if hasattr(self, 'position_var'):
            self.position_var.set("All")
        if hasattr(self, 'search_var'):
            self.search_var.set("")
        if hasattr(self, 'overall_var'):
            self.overall_var.set("0")
        if hasattr(self, 'assignment_type_var'):
            self.assignment_type_var.set("All")
        self.populate_current_tab()
    
    def on_double_click(self, event):
        """Handle double-click events."""
        selection = self.tree.selection()
        if not selection:
            return
        
        if self.current_tab == "players":
            self.scout_player()
        elif self.current_tab == "scouts":
            self.assign_scout()
        elif self.current_tab == "management":
            self.modify_assignment()
        else:  # reports
            self.view_report()
    
    def on_right_click(self, event):
        """Handle right-click events."""
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def scout_player(self):
        """Scout selected player."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player to scout.")
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        
        # Find the player object
        player = self._find_player_by_name(player_name)
        if not player:
            messagebox.showerror("Error", f"Could not find player {player_name}")
            return
        
        # Check if player is already being scouted
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'scouting_assignments'):
            if player in self.parent.game_manager.scouting_assignments:
                messagebox.showinfo("Already Scouting", f"{player_name} is already being scouted.")
                return
        
        # Get available scouts
        available_scouts = [scout for scout in self.scouts_data if not self._scout_is_busy(scout)]
        
        if not available_scouts:
            messagebox.showwarning("No Scouts Available", "All scouts are currently assigned. Please free up a scout first.")
            return
        
        # Show scout selection dialog
        self._show_scout_assignment_dialog(player, available_scouts)
    
    def view_player_profile(self):
        """View selected player's profile."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        player = self._find_player_by_name(player_name)
        
        if not player:
            messagebox.showerror("Error", f"Could not find player {player_name}")
            return
        
        # Import PlayerProfileWindow and show it
        try:
            from ui_components import PlayerProfileWindow
            
            # Check if player has scouting report
            is_scouted = False
            report = None
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                    if player.id in self.parent.game_manager.user_team.scouting_reports:
                        is_scouted = True
                        report = self.parent.game_manager.user_team.scouting_reports[player.id]
            
            PlayerProfileWindow(self.parent, player, is_scouted, report)
        except ImportError:
            messagebox.showerror("Error", "Player profile window not available.")
    
    def add_to_watchlist(self):
        """Add player to watchlist."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        player = self._find_player_by_name(player_name)
        
        if not player:
            messagebox.showerror("Error", f"Could not find player {player_name}")
            return
        
        # Create watchlist if it doesn't exist
        if not hasattr(self.parent, 'game_manager') or not hasattr(self.parent.game_manager, 'user_team'):
            messagebox.showerror("Error", "Cannot access user team")
            return
        
        if not hasattr(self.parent.game_manager.user_team, 'watchlist'):
            self.parent.game_manager.user_team.watchlist = []
        
        # Check if already in watchlist
        if player.id in [p.id for p in self.parent.game_manager.user_team.watchlist]:
            messagebox.showinfo("Already Added", f"{player_name} is already in your watchlist.")
        else:
            self.parent.game_manager.user_team.watchlist.append(player)
            messagebox.showinfo("Watchlist", f"{player_name} added to watchlist.")
    
    def assign_scout(self):
        """Assign scout to player."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to manage assignments.")
            return
        
        scout_name = self.tree.item(selection[0])['values'][0]
        scout = self._find_scout_by_name(scout_name)
        
        if not scout:
            messagebox.showerror("Error", f"Could not find scout {scout_name}")
            return
        
        # Show available players for assignment
        self._show_player_assignment_dialog(scout)
    
    def remove_assignment(self):
        """Remove scout assignment."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scout to remove assignment.")
            return
        
        scout_name = self.tree.item(selection[0])['values'][0]
        scout = self._find_scout_by_name(scout_name)
        
        if not scout:
            messagebox.showerror("Error", f"Could not find scout {scout_name}")
            return
        
        # Find and remove assignment
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'scouting_assignments'):
            player_to_remove = None
            for player, assigned_scout in self.parent.game_manager.scouting_assignments.items():
                if assigned_scout.id == scout.id:
                    player_to_remove = player
                    break
            
            if player_to_remove:
                result = messagebox.askyesno("Remove Assignment", 
                                           f"Remove {scout_name}'s assignment to scout {player_to_remove.full_name}?")
                if result:
                    del self.parent.game_manager.scouting_assignments[player_to_remove]
                    messagebox.showinfo("Assignment Removed", f"Scout assignment removed successfully.")
                    self.populate_current_tab()
            else:
                messagebox.showinfo("No Assignment", f"{scout_name} has no current assignment.")
    
    def view_report(self):
        """View scouting report."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        player = self._find_player_by_name(player_name)
        
        if not player:
            messagebox.showerror("Error", f"Could not find player {player_name}")
            return
        
        # Get the report
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
            if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                report = self.parent.game_manager.user_team.scouting_reports.get(player.id)
                if report:
                    self._show_detailed_report(player, report)
                else:
                    messagebox.showinfo("No Report", f"No scouting report found for {player_name}")
            else:
                messagebox.showinfo("No Reports", "No scouting reports available")
    
    def delete_report(self):
        """Delete scouting report."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        result = messagebox.askyesno("Delete Report", f"Delete scouting report for {player_name}?")
        
        if result:
            player = self._find_player_by_name(player_name)
            if player and hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                if hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                    if player.id in self.parent.game_manager.user_team.scouting_reports:
                        del self.parent.game_manager.user_team.scouting_reports[player.id]
                        messagebox.showinfo("Report Deleted", f"Report for {player_name} deleted.")
                        self.populate_current_tab()
                    else:
                        messagebox.showinfo("No Report", f"No report found for {player_name}")
    
    def update_views(self):
        """Update all views."""
        self._load_player_data()
        self._load_scout_data()
        self.populate_current_tab()
    
    # Management tab methods
    def create_general_assignment(self):
        """Create a new general scouting assignment."""
        dialog = tk.Toplevel(self)
        dialog.title("Create General Assignment")
        dialog.geometry("500x400")
        dialog.configure(bg=self.parent.BG_COLOR)
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Header
        tk.Label(dialog, text="Create General Scouting Assignment", 
                font=(self.parent.FONT_FAMILY, 12, "bold"),
                bg=self.parent.BG_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=15)
        
        # Main frame
        main_frame = tk.Frame(dialog, bg=self.parent.CONTENT_BG)
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Assignment type
        tk.Label(main_frame, text="Assignment Type:", 
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(anchor='w', pady=(10, 5))
        
        assignment_type_var = tk.StringVar(value="Regional")
        type_combo = ttk.Combobox(main_frame, textvariable=assignment_type_var, width=30,
                                values=["Regional", "League", "Youth", "Draft", "International"])
        type_combo.pack(fill='x', pady=(0, 10))
        
        # Region/League specification
        tk.Label(main_frame, text="Region/League/Focus:", 
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(anchor='w', pady=(0, 5))
        
        region_var = tk.StringVar()
        region_entry = tk.Entry(main_frame, textvariable=region_var, width=40)
        region_entry.pack(fill='x', pady=(0, 10))
        
        # Predefined options
        tk.Label(main_frame, text="Common Assignments:", 
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(anchor='w', pady=(10, 5))
        
        predefined_frame = tk.Frame(main_frame, bg=self.parent.CONTENT_BG)
        predefined_frame.pack(fill='x', pady=(0, 10))
        
        predefined_options = [
            ("Western Canada", "Regional"),
            ("Eastern Canada", "Regional"),
            ("Northeastern US", "Regional"),
            ("Scandinavian Europe", "Regional"),
            ("OHL", "League"),
            ("WHL", "League"),
            ("QMJHL", "League"),
            ("NCAA Division I", "League"),
            ("European Elite Leagues", "League"),
            ("2025 Draft Class", "Draft"),
            ("Youth Development (16-18)", "Youth"),
            ("International Free Agents", "International")
        ]
        
        predefined_listbox = tk.Listbox(predefined_frame, height=8, bg=self.parent.CONTENT_BG, 
                                      fg=self.parent.TEXT_COLOR, selectbackground=self.parent.ACCENT_COLOR)
        predefined_scroll = tk.Scrollbar(predefined_frame, command=predefined_listbox.yview)
        predefined_listbox.configure(yscrollcommand=predefined_scroll.set)
        
        for option, opt_type in predefined_options:
            predefined_listbox.insert(tk.END, f"{option} ({opt_type})")
        
        def select_predefined():
            selection = predefined_listbox.curselection()
            if selection:
                selected = predefined_options[selection[0]]
                region_var.set(selected[0])
                assignment_type_var.set(selected[1])
        
        predefined_listbox.bind('<Double-1>', lambda e: select_predefined())
        predefined_listbox.pack(side='left', fill='both', expand=True)
        predefined_scroll.pack(side='right', fill='y')
        
        # Scout selection
        tk.Label(main_frame, text="Assign Scout:", 
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(anchor='w', pady=(10, 5))
        
        scout_var = tk.StringVar()
        scout_combo = ttk.Combobox(main_frame, textvariable=scout_var, width=30, state='readonly')
        
        available_scouts = [scout for scout in self.scouts_data if not self._scout_is_busy(scout)]
        scout_names = [f"{scout.full_name} (Skill: {(scout.judging_player_ability + scout.judging_player_potential) / 2:.0f})" 
                      for scout in available_scouts]
        scout_combo['values'] = scout_names
        scout_combo.pack(fill='x', pady=(0, 10))
        
        # Priority
        tk.Label(main_frame, text="Priority:", 
                bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(anchor='w', pady=(0, 5))
        
        priority_var = tk.StringVar(value="Medium")
        priority_combo = ttk.Combobox(main_frame, textvariable=priority_var, width=15,
                                    values=["Low", "Medium", "High", "Critical"])
        priority_combo.pack(fill='x', pady=(0, 15))
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=self.parent.BG_COLOR)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def create_assignment():
            if not assignment_type_var.get() or not region_var.get() or not scout_var.get():
                messagebox.showwarning("Missing Information", "Please fill in all fields.")
                return
            
            # Find selected scout
            scout_index = scout_names.index(scout_var.get()) if scout_var.get() in scout_names else -1
            if scout_index == -1:
                messagebox.showerror("Error", "Invalid scout selection.")
                return
            
            selected_scout = available_scouts[scout_index]
            
            # Create assignment
            assignment = {
                'type': assignment_type_var.get(),
                'region_league': region_var.get(),
                'scout': selected_scout,
                'scout_name': selected_scout.full_name,
                'priority': priority_var.get(),
                'status': 'Active',
                'created_date': self.parent.game_manager.current_date if hasattr(self.parent, 'game_manager') else "Unknown"
            }
            
            # Store assignment
            self._store_general_assignment(assignment)
            
            messagebox.showinfo("Assignment Created", 
                              f"{selected_scout.full_name} assigned to {assignment_type_var.get()}: {region_var.get()}")
            dialog.destroy()
            self.populate_current_tab()
        
        tk.Button(button_frame, text="Create Assignment", command=create_assignment,
                 bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR).pack(side='left', padx=(0, 10))
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(side='left')
    
    def modify_assignment(self):
        """Modify an existing general assignment."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assignment to modify.")
            return
        
        assignment_type = self.tree.item(selection[0])['values'][0]
        scout_name = self.tree.item(selection[0])['values'][1]
        region_league = self.tree.item(selection[0])['values'][2]
        
        messagebox.showinfo("Modify Assignment", 
                          f"Modification dialog for {assignment_type}: {region_league} (Scout: {scout_name}) would open here.")
    
    def remove_general_assignment(self):
        """Remove a general scouting assignment."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an assignment to remove.")
            return
        
        assignment_type = self.tree.item(selection[0])['values'][0]
        scout_name = self.tree.item(selection[0])['values'][1]
        region_league = self.tree.item(selection[0])['values'][2]
        
        result = messagebox.askyesno("Remove Assignment", 
                                   f"Remove {assignment_type} assignment for {region_league}?\n\nScout: {scout_name}")
        
        if result:
            # Remove the assignment
            self._remove_general_assignment(assignment_type, scout_name, region_league)
            messagebox.showinfo("Assignment Removed", "Assignment removed successfully.")
            self.populate_current_tab()
    
    # Helper methods
    def _find_player_by_name(self, player_name):
        """Find a player object by name."""
        for player in self.players_data.get('all', []):
            if player.full_name == player_name:
                return player
        return None
    
    def _find_scout_by_name(self, scout_name):
        """Find a scout object by name."""
        for scout in self.scouts_data:
            if scout.full_name == scout_name:
                return scout
        return None
    
    def _scout_is_busy(self, scout):
        """Check if a scout is currently assigned."""
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'scouting_assignments'):
            return any(assigned_scout.id == scout.id for assigned_scout in self.parent.game_manager.scouting_assignments.values())
        return False
    
    def _show_scout_assignment_dialog(self, player, available_scouts):
        """Show dialog to assign a scout to a player."""
        dialog = tk.Toplevel(self)
        dialog.title("Assign Scout")
        dialog.geometry("400x300")
        dialog.configure(bg=self.parent.BG_COLOR)
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Header
        tk.Label(dialog, text=f"Assign Scout to {player.full_name}", 
                font=(self.parent.FONT_FAMILY, 12, "bold"),
                bg=self.parent.BG_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=10)
        
        # Scout list
        tk.Label(dialog, text="Available Scouts:", 
                bg=self.parent.BG_COLOR, fg=self.parent.TEXT_COLOR).pack(anchor='w', padx=20)
        
        scout_frame = tk.Frame(dialog, bg=self.parent.CONTENT_BG)
        scout_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        scout_listbox = tk.Listbox(scout_frame, bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        scrollbar = tk.Scrollbar(scout_frame, command=scout_listbox.yview)
        scout_listbox.configure(yscrollcommand=scrollbar.set)
        
        for scout in available_scouts:
            skill = (scout.judging_player_ability + scout.judging_player_potential) / 2
            scout_listbox.insert(tk.END, f"{scout.full_name} - Skill: {skill:.0f}")
        
        scout_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=self.parent.BG_COLOR)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def assign_selected():
            selection = scout_listbox.curselection()
            if selection:
                selected_scout = available_scouts[selection[0]]
                
                # Create assignment
                if not hasattr(self.parent, 'game_manager'):
                    self.parent.game_manager = self.parent.game_manager
                if not hasattr(self.parent.game_manager, 'scouting_assignments'):
                    self.parent.game_manager.scouting_assignments = {}
                
                self.parent.game_manager.scouting_assignments[player] = selected_scout
                
                # Create scouting report if it doesn't exist
                if hasattr(self.parent.game_manager, 'user_team'):
                    if not hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                        self.parent.game_manager.user_team.scouting_reports = {}
                    
                    if player.id not in self.parent.game_manager.user_team.scouting_reports:
                        from game_classes import ScoutingReport
                        self.parent.game_manager.user_team.scouting_reports[player.id] = ScoutingReport(
                            player=player,
                            scout=selected_scout
                        )
                
                messagebox.showinfo("Assignment Created", 
                                  f"{selected_scout.full_name} assigned to scout {player.full_name}")
                dialog.destroy()
                self.populate_current_tab()
            else:
                messagebox.showwarning("No Selection", "Please select a scout.")
        
        tk.Button(button_frame, text="Assign", command=assign_selected,
                 bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR).pack(side='left', padx=(0, 10))
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(side='left')
    
    def _show_player_assignment_dialog(self, scout):
        """Show dialog to assign a player to a scout."""
        dialog = tk.Toplevel(self)
        dialog.title("Assign Player")
        dialog.geometry("600x400")
        dialog.configure(bg=self.parent.BG_COLOR)
        dialog.resizable(True, True)
        
        # Center dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Header
        tk.Label(dialog, text=f"Assign Player to {scout.full_name}", 
                font=(self.parent.FONT_FAMILY, 12, "bold"),
                bg=self.parent.BG_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=10)
        
        # Get unassigned players
        all_players = self.players_data.get('all', [])
        assigned_players = set()
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'scouting_assignments'):
            assigned_players = set(self.parent.game_manager.scouting_assignments.keys())
        
        unassigned_players = [p for p in all_players if p not in assigned_players]
        
        # Player tree
        tree_frame = tk.Frame(dialog, bg=self.parent.CONTENT_BG)
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Name', 'Position', 'Age', 'Team', 'Overall')
        player_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            player_tree.heading(col, text=col)
            player_tree.column(col, width=100)
        
        v_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=player_tree.yview)
        player_tree.configure(yscrollcommand=v_scroll.set)
        
        for player in unassigned_players:
            try:
                player_tree.insert('', 'end', values=(
                    player.full_name,
                    player.primary_position.name,
                    player.age,
                    player.team_name,
                    player.overall_rating()
                ))
            except:
                continue
        
        player_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        
        # Buttons
        button_frame = tk.Frame(dialog, bg=self.parent.BG_COLOR)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def assign_selected():
            selection = player_tree.selection()
            if selection:
                player_name = player_tree.item(selection[0])['values'][0]
                player = self._find_player_by_name(player_name)
                
                if player:
                    # Create assignment
                    if not hasattr(self.parent, 'game_manager'):
                        self.parent.game_manager = self.parent.game_manager
                    if not hasattr(self.parent.game_manager, 'scouting_assignments'):
                        self.parent.game_manager.scouting_assignments = {}
                    
                    self.parent.game_manager.scouting_assignments[player] = scout
                    
                    # Create scouting report if it doesn't exist
                    if hasattr(self.parent.game_manager, 'user_team'):
                        if not hasattr(self.parent.game_manager.user_team, 'scouting_reports'):
                            self.parent.game_manager.user_team.scouting_reports = {}
                        
                        if player.id not in self.parent.game_manager.user_team.scouting_reports:
                            from game_classes import ScoutingReport
                            self.parent.game_manager.user_team.scouting_reports[player.id] = ScoutingReport(
                                player=player,
                                scout=scout
                            )
                    
                    messagebox.showinfo("Assignment Created", 
                                      f"{scout.full_name} assigned to scout {player.full_name}")
                    dialog.destroy()
                    self.populate_current_tab()
            else:
                messagebox.showwarning("No Selection", "Please select a player.")
        
        tk.Button(button_frame, text="Assign", command=assign_selected,
                 bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR).pack(side='left', padx=(0, 10))
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR).pack(side='left')
    
    def _show_detailed_report(self, player, report):
        """Show detailed scouting report window."""
        report_window = tk.Toplevel(self)
        report_window.title(f"Scouting Report - {player.full_name}")
        report_window.geometry("700x600")
        report_window.configure(bg=self.parent.BG_COLOR)
        report_window.resizable(True, True)
        
        # Center window
        report_window.transient(self)
        
        # Header
        header_frame = tk.Frame(report_window, bg=self.parent.TITLE_BAR_COLOR, height=50)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=f"SCOUTING REPORT - {player.full_name.upper()}", 
                font=(self.parent.FONT_FAMILY, 14, "bold"),
                bg=self.parent.TITLE_BAR_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=15)
        
        # Content frame with scrollbar
        content_frame = tk.Frame(report_window, bg=self.parent.CONTENT_BG)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Create text widget with scrollbar
        text_frame = tk.Frame(content_frame, bg=self.parent.CONTENT_BG)
        text_frame.pack(fill='both', expand=True)
        
        text_widget = tk.Text(text_frame, wrap='word', bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR, font=(self.parent.FONT_FAMILY, 10))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Generate report content
        report_content = self._generate_report_content(player, report)
        text_widget.insert('1.0', report_content)
        text_widget.config(state='disabled')
        
        scrollbar.pack(side='right', fill='y')
        text_widget.pack(side='left', fill='both', expand=True)
        
        # Close button
        tk.Button(content_frame, text="Close", command=report_window.destroy,
                 bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR).pack(pady=10)
    
    def _generate_report_content(self, player, report):
        """Generate detailed report content."""
        content = f"SCOUTING REPORT\n"
        content += "=" * 50 + "\n\n"
        
        content += f"Player: {player.full_name}\n"
        content += f"Position: {player.primary_position.name}\n"
        content += f"Age: {player.age}\n"
        content += f"Team: {player.team_name}\n"
        content += f"Overall Rating: {player.overall_rating()}\n\n"
        
        content += f"Scout: {report.scout.full_name}\n"
        content += f"Viewings: {report.viewings}/15\n"
        content += f"Accuracy: {report.accuracy}\n"
        if report.last_viewed:
            content += f"Last Viewed: {report.last_viewed.strftime('%m/%d/%Y')}\n"
        content += "\n"
        
        if report.scouted_potential:
            content += f"Potential: {report.scouted_potential}\n"
        
        if report.strengths:
            content += f"Strengths: {', '.join(report.strengths)}\n"
        
        if report.weaknesses:
            content += f"Weaknesses: {', '.join(report.weaknesses)}\n"
        
        if report.notes:
            content += f"\nNotes:\n{report.notes}\n"
        
        # Add some basic attribute analysis if available
        content += "\nATTRIBUTE ANALYSIS\n"
        content += "-" * 20 + "\n"
        
        if player.primary_position.name == 'G':
            content += f"Goaltending: {player.goaltending}\n"
            content += f"Reflexes: {player.reflexes}\n" 
            content += f"Positioning: {player.positioning}\n"
        else:
            content += f"Skating: {player.skating}\n"
            content += f"Shooting: {player.shooting}\n"
            content += f"Passing: {player.passing}\n"
            content += f"Checking: {player.checking}\n"
            content += f"Hockey IQ: {player.hockey_iq}\n"
        
        return content
    
    # General assignment management methods
    def _get_general_assignments(self):
        """Get all general scouting assignments."""
        # Initialize general assignments if they don't exist
        if not hasattr(self.parent, 'game_manager'):
            return []
        
        if not hasattr(self.parent.game_manager, 'general_scouting_assignments'):
            self.parent.game_manager.general_scouting_assignments = []
        
        return self.parent.game_manager.general_scouting_assignments
    
    def _store_general_assignment(self, assignment):
        """Store a new general assignment."""
        if not hasattr(self.parent, 'game_manager'):
            return
        
        if not hasattr(self.parent.game_manager, 'general_scouting_assignments'):
            self.parent.game_manager.general_scouting_assignments = []
        
        self.parent.game_manager.general_scouting_assignments.append(assignment)
    
    def _remove_general_assignment(self, assignment_type, scout_name, region_league):
        """Remove a general assignment."""
        if not hasattr(self.parent, 'game_manager'):
            return
        
        if not hasattr(self.parent.game_manager, 'general_scouting_assignments'):
            return
        
        # Find and remove the assignment
        assignments = self.parent.game_manager.general_scouting_assignments
        for i, assignment in enumerate(assignments):
            if (assignment['type'] == assignment_type and 
                assignment['scout_name'] == scout_name and 
                assignment['region_league'] == region_league):
                del assignments[i]
                break
