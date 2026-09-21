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
        
        # Initialize data
        self.current_tab = "players"
        self.players_data = {}
        self.scouts_data = []
        
        # Load data
        self._load_player_data()
        self._load_scout_data()
        
        # Create UI
        self.create_interface()
        self.populate_current_tab()
        
        # Track window
        self.parent.open_windows['scouting'] = self
        self.focus_set()
    
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
                self.scouts_data = [staff for staff in self.parent.game_manager.user_team.staff 
                                  if 'SCOUT' in staff.role.value.upper()]
            print(f"Loaded {len(self.scouts_data)} scouts")
        except Exception as e:
            print(f"Error loading scout data: {e}")
            self.scouts_data = []
    
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
            
            # Position filter
            tk.Label(self.filters_frame, text="Position:", bg=self.parent.CONTENT_BG, 
                    fg=self.parent.TEXT_COLOR).pack(side='left', padx=(0, 5))
            
            self.position_var = tk.StringVar(value="All")
            position_combo = ttk.Combobox(self.filters_frame, textvariable=self.position_var, 
                                        width=10, values=["All", "C", "LW", "RW", "LD", "RD", "D", "G"])
            position_combo.pack(side='left', padx=(0, 20))
            position_combo.bind('<<ComboboxSelected>>', lambda e: self.populate_current_tab())
            
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
            
            # Clear button
            tk.Button(self.filters_frame, text="Clear Filters", 
                     bg=self.parent.ACCENT_COLOR, fg=self.parent.HEADER_COLOR,
                     command=self.clear_filters).pack(side='left', padx=10)
    
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
                
                if hasattr(self.parent, 'scouting_assignments'):
                    for player, assigned_scout in self.parent.scouting_assignments.items():
                        if assigned_scout.id == scout.id:
                            assigned_player = player.full_name
                            # Get progress from reports
                            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
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
        messagebox.showinfo("Scout Player", f"Scouting assignment for {player_name} would be created here.")
    
    def view_player_profile(self):
        """View selected player's profile."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        messagebox.showinfo("Player Profile", f"Player profile for {player_name} would open here.")
    
    def add_to_watchlist(self):
        """Add player to watchlist."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        messagebox.showinfo("Watchlist", f"{player_name} added to watchlist.")
    
    def assign_scout(self):
        """Assign scout to player."""
        messagebox.showinfo("Assign Scout", "Scout assignment functionality would be implemented here.")
    
    def remove_assignment(self):
        """Remove scout assignment."""
        messagebox.showinfo("Remove Assignment", "Assignment removal functionality would be implemented here.")
    
    def view_report(self):
        """View scouting report."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        messagebox.showinfo("Scouting Report", f"Detailed report for {player_name} would be shown here.")
    
    def delete_report(self):
        """Delete scouting report."""
        selection = self.tree.selection()
        if not selection:
            return
        
        player_name = self.tree.item(selection[0])['values'][0]
        result = messagebox.askyesno("Delete Report", f"Delete scouting report for {player_name}?")
        if result:
            messagebox.showinfo("Report Deleted", f"Report for {player_name} deleted.")
    
    def update_views(self):
        """Update all views."""
        self._load_player_data()
        self._load_scout_data()
        self.populate_current_tab()
