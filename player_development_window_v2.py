"""
Completely rewritten Player Development Window
Shows letter grades with proper color coding and column sorting
"""

import tkinter as tk
from tkinter import ttk
from player_development_system import (
    PlayerDevelopmentEngine, DevelopmentStage, 
    PlayerPotential, initialize_player_potential
)


class PlayerDevelopmentWindowV2(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Player Development Center")
        self.geometry("1200x800")
        self.configure(background=parent.BG_COLOR)
        
        # Initialize development engine
        self.dev_engine = PlayerDevelopmentEngine()
        
        # Track sorting state and data - Initialize BEFORE creating interface
        self._sort_reverse = {}
        self.player_data = []
        
        # Initialize potentials for existing players
        self._initialize_player_potentials()
        
        # Create the interface
        self._create_interface()
        self._populate_player_list()
        
        # Track window for lifecycle management
        self.parent.open_windows['development'] = self
        
    def _initialize_player_potentials(self):
        """Initialize potential for players that don't have it"""
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
            
            for player in all_players:
                if not hasattr(player, 'potential'):
                    player.potential = initialize_player_potential(player)
                    
    def _create_interface(self):
        """Create the main interface"""
        # Main paned window for resizable layout
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style='TPanedwindow')
        main_paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left panel - Player list
        left_panel = ttk.LabelFrame(main_paned, text="Team Players", style='Card.TLabelframe')
        main_paned.add(left_panel, weight=2)
        
        # Player list treeview with proper columns
        columns = {
            'name': ('Player Name', 180),
            'age': ('Age', 50),
            'pos': ('Position', 70),
            'overall': ('Overall', 70),
            'potential': ('Potential', 80),
            'stage': ('Dev Stage', 100),
        }
        
        # Create treeview
        tree_frame = ttk.Frame(left_panel)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.player_tree = ttk.Treeview(tree_frame, columns=list(columns.keys()), 
                                       show='headings', height=25)
        
        # Configure columns with sorting
        for col_id, (header, width) in columns.items():
            self.player_tree.heading(col_id, text=header, 
                                    command=lambda c=col_id: self._sort_by_column(c))
            self.player_tree.column(col_id, width=width, anchor='center')
            
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.player_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.player_tree.xview)
        self.player_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for scrollbars
        self.player_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # Configure potential grade color tags
        self._configure_color_tags()
        
        # Bind selection event
        self.player_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        
        # Right panel - Player details
        right_panel = ttk.LabelFrame(main_paned, text="Development Details", style='Card.TLabelframe')
        main_paned.add(right_panel, weight=1)
        
        # Create scrollable details area
        self._create_details_panel(right_panel)
        
    def _configure_color_tags(self):
        """Configure color tags for potential grades"""
        # Clear any existing position-based colors first
        position_tags = ['center', 'wing', 'defense', 'goalie', 'high_morale', 'med_morale', 'low_morale', 'vlow_morale']
        for tag in position_tags:
            try:
                self.player_tree.tag_configure(tag, background='', foreground='')
            except:
                pass
        
        # Configure potential grade colors to match main game
        self.player_tree.tag_configure('grade_A_plus', background='#1A9B00', foreground='#FFFFFF')  # A+
        self.player_tree.tag_configure('grade_A', background='#1A9B00', foreground='#FFFFFF')       # A
        self.player_tree.tag_configure('grade_A_minus', background='#4CAF50', foreground='#FFFFFF') # A-
        self.player_tree.tag_configure('grade_B_plus', background='#4CAF50', foreground='#FFFFFF')  # B+
        self.player_tree.tag_configure('grade_B', background='#8BC34A', foreground='#FFFFFF')       # B
        self.player_tree.tag_configure('grade_B_minus', background='#8BC34A', foreground='#FFFFFF') # B-
        self.player_tree.tag_configure('grade_C_plus', background='#FFC107', foreground='#000000')  # C+
        self.player_tree.tag_configure('grade_C', background='#FFC107', foreground='#000000')       # C
        self.player_tree.tag_configure('grade_C_minus', background='#FF9800', foreground='#FFFFFF') # C-
        self.player_tree.tag_configure('grade_D', background='#FF9800', foreground='#FFFFFF')       # D
        self.player_tree.tag_configure('grade_F', background='#FF5722', foreground='#FFFFFF')       # F
        
    def _create_details_panel(self, parent):
        """Create the player details panel"""
        # Scrollable frame setup
        canvas = tk.Canvas(parent, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, style='Content.TFrame')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Initial empty state
        self._show_no_selection_message()
        
    def _show_no_selection_message(self):
        """Show message when no player is selected"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        ttk.Label(self.scrollable_frame, 
                 text="Select a player to view development details",
                 style='Title.TLabel').pack(pady=50)
                 
    def _populate_player_list(self):
        """Populate the player list with letter grades and colors"""
        # Clear existing items
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        self.player_data = []
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        # Get all players
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Process each player
        for player in all_players:
            summary = self.dev_engine.get_player_development_summary(player)
            
            # Create display values with letter grade
            values = (
                player.full_name,
                player.age,
                player.primary_position.value,
                summary['current_overall'],
                player.potential_grade,  # Show actual letter grade
                summary['development_stage'].title()
            )
            
            # Determine color tag based on potential grade
            grade = player.potential_grade
            color_tag = self._get_color_tag_for_grade(grade)
            
            # Insert item with color tag
            item_id = self.player_tree.insert('', 'end', values=values, tags=(color_tag,))
            
            # Store data for sorting
            player_data = {
                'item_id': item_id,
                'player': player,
                'values': values,
                'tag': color_tag
            }
            self.player_data.append(player_data)
            
    def _get_color_tag_for_grade(self, grade):
        """Convert potential grade to color tag name"""
        grade_map = {
            'A+': 'grade_A_plus',
            'A': 'grade_A', 
            'A-': 'grade_A_minus',
            'B+': 'grade_B_plus',
            'B': 'grade_B',
            'B-': 'grade_B_minus', 
            'C+': 'grade_C_plus',
            'C': 'grade_C',
            'C-': 'grade_C_minus',
            'D': 'grade_D',
            'F': 'grade_F'
        }
        return grade_map.get(grade, 'grade_F')
        
    def _sort_by_column(self, col):
        """Sort the treeview by the specified column"""
        # Toggle sort direction
        if col not in self._sort_reverse:
            self._sort_reverse[col] = False
        else:
            self._sort_reverse[col] = not self._sort_reverse[col]
            
        reverse = self._sort_reverse[col]
        
        # Get column index for sorting
        columns = ['name', 'age', 'pos', 'overall', 'potential', 'stage']
        col_index = columns.index(col)
        
        # Sort the stored data
        def sort_key(item):
            value = item['values'][col_index]
            # Handle numeric columns
            if col in ['age', 'overall']:
                try:
                    return int(value)
                except:
                    return 0
            # Handle potential grades (special sorting)
            elif col == 'potential':
                grade_order = {'A+': 11, 'A': 10, 'A-': 9, 'B+': 8, 'B': 7, 'B-': 6, 
                              'C+': 5, 'C': 4, 'C-': 3, 'D': 2, 'F': 1}
                return grade_order.get(value, 0)
            else:
                return str(value).lower()
                
        self.player_data.sort(key=sort_key, reverse=reverse)
        
        # Rebuild treeview with sorted data
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
            
        for data in self.player_data:
            item_id = self.player_tree.insert('', 'end', values=data['values'], tags=(data['tag'],))
            data['item_id'] = item_id
            
        # Update column heading to show sort direction
        for c in columns:
            if c == col:
                symbol = " ↓" if reverse else " ↑"
                header_text = {
                    'name': 'Player Name', 'age': 'Age', 'pos': 'Position', 
                    'overall': 'Overall', 'potential': 'Potential', 'stage': 'Dev Stage'
                }[c] + symbol
            else:
                header_text = {
                    'name': 'Player Name', 'age': 'Age', 'pos': 'Position',
                    'overall': 'Overall', 'potential': 'Potential', 'stage': 'Dev Stage'
                }[c]
            self.player_tree.heading(c, text=header_text)
            
    def _on_player_select(self, event):
        """Handle player selection"""
        selection = self.player_tree.selection()
        if not selection:
            self._show_no_selection_message()
            return
            
        # Find selected player
        selected_item = selection[0]
        selected_player = None
        
        for data in self.player_data:
            if data['item_id'] == selected_item:
                selected_player = data['player']
                break
                
        if selected_player:
            self._show_player_details(selected_player)
            
    def _show_player_details(self, player):
        """Show detailed development information for selected player"""
        # Clear existing details
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Player header
        header_frame = ttk.Frame(self.scrollable_frame, style='Content.TFrame')
        header_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        ttk.Label(header_frame, text=player.full_name, 
                 style='Title.TLabel').pack(anchor='w')
        ttk.Label(header_frame, 
                 text=f"{player.age} years old • {player.primary_position.value} • Overall: {player.overall_rating()}", 
                 style='TLabel').pack(anchor='w')
                 
        # Potential section
        potential_frame = ttk.LabelFrame(self.scrollable_frame, text="Potential Assessment", style='Card.TLabelframe')
        potential_frame.pack(fill='x', padx=10, pady=5)
        
        pot_info = ttk.Frame(potential_frame, style='Content.TFrame')
        pot_info.pack(fill='x', padx=10, pady=10)
        
        # Create colored potential grade display
        grade_frame = ttk.Frame(pot_info, style='Content.TFrame')
        grade_frame.pack(fill='x', pady=5)
        
        ttk.Label(grade_frame, text="Potential Grade:", style='TLabel').pack(side='left')
        
        # Color-coded potential grade
        grade_colors = {
            'A+': '#1A9B00', 'A': '#1A9B00', 'A-': '#4CAF50', 'B+': '#4CAF50',
            'B': '#8BC34A', 'B-': '#8BC34A', 'C+': '#FFC107', 'C': '#FFC107',
            'C-': '#FF9800', 'D': '#FF9800', 'F': '#FF5722'
        }
        
        grade_color = grade_colors.get(player.potential_grade, '#FF5722')
        grade_label = tk.Label(grade_frame, text=f" {player.potential_grade} ", 
                              bg=grade_color, fg='#FFFFFF' if grade_color != '#FFC107' else '#000000',
                              font=(self.parent.FONT_FAMILY, 10, 'bold'), relief='solid', bd=1)
        grade_label.pack(side='left', padx=(10, 0))
        
        # Development summary
        summary = self.dev_engine.get_player_development_summary(player)
        
        ttk.Label(pot_info, text=f"Development Stage: {summary['development_stage'].title()}", 
                 style='TLabel').pack(anchor='w', pady=2)
        ttk.Label(pot_info, text=f"Current Overall: {summary['current_overall']}", 
                 style='TLabel').pack(anchor='w', pady=2)
        ttk.Label(pot_info, text=f"Potential Overall: {summary['potential_overall']}", 
                 style='TLabel').pack(anchor='w', pady=2)
        ttk.Label(pot_info, text=f"Outlook: {summary['development_outlook']}", 
                 style='TLabel').pack(anchor='w', pady=2)
                 
        # Training section (preserve existing functionality)
        training_frame = ttk.LabelFrame(self.scrollable_frame, text="Training Programs", style='Card.TLabelframe')
        training_frame.pack(fill='x', padx=10, pady=5)
        
        training_info = ttk.Frame(training_frame, style='Content.TFrame')
        training_info.pack(fill='x', padx=10, pady=10)
        
        # Check if player is in training
        if player.id in self.dev_engine.active_training_programs:
            program = self.dev_engine.active_training_programs[player.id]
            ttk.Label(training_info, text=f"Currently training: {program.focus_attribute.title()}", 
                     style='TLabel').pack(anchor='w')
            ttk.Label(training_info, text=f"Days remaining: {program.duration - program.days_completed}", 
                     style='TLabel').pack(anchor='w')
        else:
            ttk.Label(training_info, text="No active training program", 
                     style='TLabel').pack(anchor='w')
                     
        # Add training controls here (buttons, etc.) - preserve existing functionality
        control_frame = ttk.Frame(training_info, style='Content.TFrame')
        control_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(control_frame, text="Assign Training", 
                  command=lambda: self._show_training_options(player)).pack(side='left', padx=(0, 10))
                  
        if player.id in self.dev_engine.active_training_programs:
            ttk.Button(control_frame, text="Cancel Training",
                      command=lambda: self._cancel_training(player)).pack(side='left')
                      
    def _show_training_options(self, player):
        """Show training assignment dialog"""
        # This would open a training assignment window
        # Preserve existing training functionality
        pass
        
    def _cancel_training(self, player):
        """Cancel player's current training"""
        if player.id in self.dev_engine.active_training_programs:
            del self.dev_engine.active_training_programs[player.id]
            self._show_player_details(player)  # Refresh details
            
    def update_views(self):
        """Update the window views"""
        self._populate_player_list()
        self._show_no_selection_message()