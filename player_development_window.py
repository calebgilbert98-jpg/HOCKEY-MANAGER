"""
Player Development Management Window
UI for managing player training, development tracking, and potential monitoring
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List
from datetime import date, timedelta
from player_development_system import (
    PlayerDevelopmentEngine, TrainingFocus, DevelopmentStage,
    PlayerPotential, initialize_player_potential
)


class PlayerDevelopmentWindow(tk.Toplevel):
    """Window for managing player development and training"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Player Development Center")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1200x800")
        self.minsize(800, 600)  # Set minimum size
        self.resizable(True, True)  # Allow resizing
        
        # Initialize development engine if not present
        if not hasattr(parent, 'development_engine'):
            parent.development_engine = PlayerDevelopmentEngine()
        
        self.dev_engine = parent.development_engine
        
        # Initialize potentials for existing players
        self._initialize_player_potentials()
        
        self._create_interface()
        self._populate_player_list()
        
        # Track window for lifecycle management
        self.parent.open_windows['development'] = self
        
        # Bind window resize to update canvas sizing
        self.bind('<Configure>', self._on_window_resize)
    
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
        """Create the main development interface"""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self, style='Custom.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self._create_development_overview_tab()
        self._create_training_programs_tab()
        self._create_development_history_tab()
        
        # Control buttons at bottom
        control_frame = ttk.Frame(self, style='Content.TFrame')
        control_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        ttk.Button(control_frame, text="📊 Update All Players", 
                  command=self._update_all_views, style='TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(control_frame, text="📈 Process Monthly Development", 
                  command=self._process_monthly_development, style='TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(control_frame, text="❌ Close", 
                  command=self.destroy, style='TButton').pack(side='right')
    
    def _create_development_overview_tab(self):
        """Create the development overview tab"""
        tab_frame = ttk.Frame(self.notebook, style='Content.TFrame')
        self.notebook.add(tab_frame, text="📈 Development Overview")
        
        # Split into left (player list) and right (details)
        paned_window = ttk.PanedWindow(tab_frame, orient='horizontal')
        paned_window.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Player list (fixed width, doesn't expand much)
        left_frame = ttk.LabelFrame(paned_window, text="Team Players", style='Card.TLabelframe')
        paned_window.add(left_frame, weight=1, minsize=500)
        
        # Player treeview with proper sizing
        columns = {
            'name': ('Player', 150),
            'age': ('Age', 50),
            'pos': ('Pos', 50),
            'overall': ('Overall', 70),
            'potential': ('Potential', 70),
            'stage': ('Stage', 100),
            'outlook': ('Outlook', 150)
        }
        
        self.player_tree = ttk.Treeview(left_frame, columns=list(columns.keys()), 
                                       show='headings', height=20)
        
        # Configure column headings with sorting functionality
        for col_id, (header, width) in columns.items():
            self.player_tree.heading(col_id, text=header, 
                                    command=lambda c=col_id: self._sort_column(c, False))
            self.player_tree.column(col_id, width=width, anchor='center')
        
        # Track sorting state
        self._sort_reverse = False
        self._sort_column_id = None
        
        # Scrollbar for player list
        player_scrollbar = ttk.Scrollbar(left_frame, orient='vertical', command=self.player_tree.yview)
        self.player_tree.configure(yscrollcommand=player_scrollbar.set)
        
        self.player_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        player_scrollbar.pack(side='right', fill='y', pady=10)
        
        # COMPLETELY OVERRIDE position-based color system with potential-based colors
        # Configure potential-based color tags to match the main game's color scheme
        self.player_tree.tag_configure('excellent_potential', 
                                      background='#1A9B00', foreground='#FFFFFF')  # A+, A grades - Dark green
        self.player_tree.tag_configure('high_potential', 
                                      background='#4CAF50', foreground='#FFFFFF')  # A-, B+ grades - Medium green
        self.player_tree.tag_configure('moderate_potential', 
                                      background='#8BC34A', foreground='#FFFFFF')  # B, B- grades - Light green
        self.player_tree.tag_configure('limited_potential', 
                                      background='#FFC107', foreground='#000000')  # C+, C grades - Yellow
        self.player_tree.tag_configure('poor_potential', 
                                      background='#FF9800', foreground='#FFFFFF')  # C-, D, F grades - Orange
        
        # Bind selection event
        self.player_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        
        # Store player data for sorting
        self.player_data = []
        
        # Right side - Player details (expands more when window is resized)
        right_frame = ttk.LabelFrame(paned_window, text="Development Details", style='Card.TLabelframe')
        paned_window.add(right_frame, weight=3, minsize=400)
        
        # Create scrollable detail area that fills the entire right frame
        detail_container = ttk.Frame(right_frame, style='Content.TFrame')
        detail_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Configure the container grid to expand properly
        detail_container.grid_columnconfigure(0, weight=1)
        detail_container.grid_rowconfigure(0, weight=1)
        
        self.detail_canvas = tk.Canvas(detail_container, bg=self.parent.CONTENT_BG, highlightthickness=0)
        detail_scrollbar = ttk.Scrollbar(detail_container, orient="vertical", command=self.detail_canvas.yview)
        self.detail_frame = ttk.Frame(self.detail_canvas, style='Content.TFrame')
        
        # Configure detail_frame to expand horizontally
        self.detail_frame.grid_columnconfigure(0, weight=1)
        
        # Configure scroll region updating
        self.detail_frame.bind(
            "<Configure>",
            lambda e: self._on_canvas_configure_frame()
        )
        
        # Configure canvas window to expand with canvas
        self.detail_canvas.bind(
            "<Configure>",
            lambda e: self._on_canvas_configure_resize(e)
        )
        
        self.canvas_window = self.detail_canvas.create_window((0, 0), window=self.detail_frame, anchor="nw")
        self.detail_canvas.configure(yscrollcommand=detail_scrollbar.set)
        
        # Pack canvas and scrollbar to fill container
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        detail_scrollbar.pack(side="right", fill="y")
        
        # Schedule initial size update after widget creation
        self.after_idle(self._initial_canvas_setup)
        
        # Default message
        self.default_label = ttk.Label(self.detail_frame, 
                                     text="Select a player to view development details",
                                     style='Content.TLabel')
        self.default_label.pack(pady=50)
    
    def _create_training_programs_tab(self):
        """Create the training programs tab"""
        tab_frame = ttk.Frame(self.notebook, style='Content.TFrame')
        self.notebook.add(tab_frame, text="🏋️ Training Programs")
        
        # Main container
        main_container = ttk.Frame(tab_frame, style='Content.TFrame')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Active training programs section
        active_frame = ttk.LabelFrame(main_container, text="Active Training Programs", style='Card.TLabelframe')
        active_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Active training treeview
        training_columns = {
            'player': ('Player', 150),
            'focus': ('Focus', 100),
            'intensity': ('Intensity', 80),
            'progress': ('Progress', 100),
            'trainer': ('Trainer Quality', 120),
            'completion': ('Est. Completion', 100)
        }
        
        self.training_tree = ttk.Treeview(active_frame, columns=list(training_columns.keys()), 
                                         show='headings', height=8)
        
        for col_id, (header, width) in training_columns.items():
            self.training_tree.heading(col_id, text=header)
            self.training_tree.column(col_id, width=width, anchor='center')
        
        training_scrollbar = ttk.Scrollbar(active_frame, orient='vertical', command=self.training_tree.yview)
        self.training_tree.configure(yscrollcommand=training_scrollbar.set)
        
        self.training_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        training_scrollbar.pack(side='right', fill='y', pady=10)
        
        # New training program section
        new_training_frame = ttk.LabelFrame(main_container, text="Start New Training Program", style='Card.TLabelframe')
        new_training_frame.pack(fill='x')
        
        # Training form
        form_frame = ttk.Frame(new_training_frame, style='Content.TFrame')
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Player selection
        ttk.Label(form_frame, text="Player:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.training_player_var = tk.StringVar(master=self)
        self.training_player_combo = ttk.Combobox(form_frame, textvariable=self.training_player_var, 
                                                 state='readonly', width=20)
        self.training_player_combo.grid(row=0, column=1, padx=(0, 20))
        
        # Training focus
        ttk.Label(form_frame, text="Focus:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=(0, 10))
        self.training_focus_var = tk.StringVar(master=self)
        focus_options = [focus.value.title() for focus in TrainingFocus]
        self.training_focus_combo = ttk.Combobox(form_frame, textvariable=self.training_focus_var,
                                               values=focus_options, state='readonly', width=15)
        self.training_focus_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Intensity
        ttk.Label(form_frame, text="Intensity (1-10):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=(0, 10))
        self.intensity_var = tk.StringVar(master=self, value="5")
        intensity_spin = ttk.Spinbox(form_frame, from_=1, to=10, textvariable=self.intensity_var, width=10)
        intensity_spin.grid(row=1, column=1, padx=(0, 20))
        
        # Duration
        ttk.Label(form_frame, text="Duration (weeks):", style='Content.TLabel').grid(row=1, column=2, sticky='w', padx=(0, 10))
        self.duration_var = tk.StringVar(master=self, value="8")
        duration_spin = ttk.Spinbox(form_frame, from_=2, to=24, textvariable=self.duration_var, width=10)
        duration_spin.grid(row=1, column=3, padx=(0, 20))
        
        # Trainer quality
        ttk.Label(form_frame, text="Trainer Quality:", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=(0, 10))
        self.trainer_quality_var = tk.StringVar(master=self)
        trainer_options = ["Basic (10)", "Good (13)", "Excellent (16)", "Elite (18)"]
        self.trainer_combo = ttk.Combobox(form_frame, textvariable=self.trainer_quality_var,
                                        values=trainer_options, state='readonly', width=15)
        self.trainer_combo.set("Good (13)")
        self.trainer_combo.grid(row=2, column=1, columnspan=2, padx=(0, 20))
        
        # Start button
        start_btn = ttk.Button(form_frame, text="🏋️ Start Training", 
                              command=self._start_training_program, style='Accent.TButton')
        start_btn.grid(row=2, column=3, padx=(0, 10))
    
    def _create_development_history_tab(self):
        """Create the development history tab"""
        tab_frame = ttk.Frame(self.notebook, style='Content.TFrame')
        self.notebook.add(tab_frame, text="📚 Development History")
        
        # Player selection for history
        selection_frame = ttk.Frame(tab_frame, style='Content.TFrame')
        selection_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(selection_frame, text="View History for:", style='Content.TLabel').pack(side='left')
        self.history_player_var = tk.StringVar(master=self)
        self.history_player_combo = ttk.Combobox(selection_frame, textvariable=self.history_player_var,
                                               state='readonly', width=30)
        self.history_player_combo.pack(side='left', padx=(10, 0))
        self.history_player_combo.bind('<<ComboboxSelected>>', self._on_history_player_select)
        
        # History display
        history_frame = ttk.LabelFrame(tab_frame, text="Development History", style='Card.TLabelframe')
        history_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # History treeview
        history_columns = {
            'date': ('Date', 100),
            'attribute': ('Attribute', 120),
            'change': ('Change', 80),
            'reason': ('Reason', 200),
            'new_value': ('New Value', 80)
        }
        
        self.history_tree = ttk.Treeview(history_frame, columns=list(history_columns.keys()),
                                        show='headings', height=15)
        
        for col_id, (header, width) in history_columns.items():
            self.history_tree.heading(col_id, text=header)
            self.history_tree.column(col_id, width=width, anchor='center')
        
        history_scrollbar = ttk.Scrollbar(history_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        history_scrollbar.pack(side='right', fill='y', pady=10)
    
    def _populate_player_list(self):
        """Populate the player list with team players"""
        # Clear existing items
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
        
        # Get all players
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Populate treeview with potential-based color coding (override any existing colors)
        for player in all_players:
            summary = self.dev_engine.get_player_development_summary(player)
            
            values = (
                player.full_name,
                player.age,
                player.primary_position.value,
                summary['current_overall'],
                player.potential_grade,  # Show letter grade instead of descriptive text
                summary['development_stage'].title(),
                summary['development_outlook']
            )
            
            # Determine potential tag based on the letter grade (which is now displayed)
            grade = player.potential_grade
            if grade in ['A+', 'A']:
                potential_tag = 'excellent_potential'  # Dark green
            elif grade in ['A-', 'B+']:
                potential_tag = 'high_potential'       # Medium green  
            elif grade in ['B', 'B-']:
                potential_tag = 'moderate_potential'   # Light green
            elif grade in ['C+', 'C']:
                potential_tag = 'limited_potential'    # Yellow
            else:  # C-, D, F, etc.
                potential_tag = 'poor_potential'       # Orange
            
            # Insert item with ONLY our potential tag
            item_id = self.player_tree.insert('', 'end', values=values, tags=(potential_tag,))
            
            # Store player reference
            self.player_tree.set(item_id, 'player_obj', player)
        
        # Update training combo options
        self._update_training_combos()
        
        # Override position tag colors AFTER all items are populated
        self._override_position_tag_colors()
    
    def _override_position_tag_colors(self):
        """Override any position-based tag colors that might interfere with potential colors"""
        # Clear position-based tags by setting them to transparent/empty
        self.player_tree.tag_configure('center', background='', foreground='')
        self.player_tree.tag_configure('wing', background='', foreground='')
        self.player_tree.tag_configure('defense', background='', foreground='')
        self.player_tree.tag_configure('goalie', background='', foreground='')
        
        # Clear morale tags too
        self.player_tree.tag_configure('high_morale', background='', foreground='')
        self.player_tree.tag_configure('med_morale', background='', foreground='')
        self.player_tree.tag_configure('low_morale', background='', foreground='')
        self.player_tree.tag_configure('vlow_morale', background='', foreground='')
    
    def _force_apply_color(self, item_id, tag):
        """Force apply potential-based color to tree item, overriding any existing colors"""
        try:
            if self.player_tree.exists(item_id):
                # Clear any existing tags first
                self.player_tree.set(item_id, '#0', '')  # Clear item tags
                # Reapply only our potential tag
                current_tags = list(self.player_tree.item(item_id, 'tags'))
                # Remove any position-based tags
                filtered_tags = [t for t in current_tags if t not in ['center', 'wing', 'defense', 'goalie']]
                # Add our potential tag if not already there
                if tag not in filtered_tags:
                    filtered_tags.append(tag)
                self.player_tree.item(item_id, tags=filtered_tags)
        except Exception as e:
            print(f"Warning: Could not apply color to item {item_id}: {e}")
    
    def _update_training_combos(self):
        """Update the training program combo boxes"""
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
        
        # Get available players (not currently in training)
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        available_players = []
        for player in all_players:
            if player.id not in self.dev_engine.active_training_programs:
                available_players.append(f"{player.full_name} ({player.primary_position.value})")
        
        # Update training player combo
        self.training_player_combo['values'] = available_players
        
        # Update history player combo
        all_player_names = [f"{p.full_name} ({p.primary_position.value})" for p in all_players]
        self.history_player_combo['values'] = all_player_names
    
    def _on_player_select(self, event):
        """Handle player selection in the overview"""
        selection = self.player_tree.selection()
        if not selection:
            return
        
        # Get selected player
        item = selection[0]
        player = self.player_tree.set(item, 'player_obj')
        
        if player:
            self._show_player_details(player)
    
    def _get_potential_color(self, current_value, potential_value):
        """Get color coding for potential ratings"""
        difference = potential_value - current_value
        
        if difference >= 4:
            return '#00FF00'  # Bright green - excellent potential
        elif difference >= 2:
            return '#90EE90'  # Light green - good potential  
        elif difference >= 1:
            return '#FFFF00'  # Yellow - moderate potential
        elif difference >= 0:
            return '#FFA500'  # Orange - limited potential
        else:
            return '#FF6B6B'  # Red - declining/poor potential
    
    def _get_overall_potential_color(self, current_overall, potential_overall):
        """Get color coding for overall potential ratings"""
        difference = potential_overall - current_overall
        
        if difference >= 5:
            return '#00FF00'  # Bright green - star potential
        elif difference >= 3:
            return '#90EE90'  # Light green - high potential
        elif difference >= 1:
            return '#FFFF00'  # Yellow - moderate potential
        elif difference >= 0:
            return '#FFA500'  # Orange - limited potential
        else:
            return '#FF6B6B'  # Red - declining potential
    
    def _get_development_rate_color(self, development_rate):
        """Get color coding for development rate"""
        if development_rate >= 0.5:
            return '#00FF00'  # Bright green - excellent development
        elif development_rate >= 0.2:
            return '#90EE90'  # Light green - good development
        elif development_rate >= 0.0:
            return '#FFFF00'  # Yellow - average development
        elif development_rate >= -0.2:
            return '#FFA500'  # Orange - poor development
        else:
            return '#FF6B6B'  # Red - declining
    
    def _get_outlook_color(self, outlook):
        """Get color coding for development outlook"""
        outlook_lower = outlook.lower()
        if 'excellent' in outlook_lower or 'superstar' in outlook_lower:
            return '#00FF00'  # Bright green - excellent outlook
        elif 'very good' in outlook_lower or 'high' in outlook_lower:
            return '#90EE90'  # Light green - very good outlook
        elif 'good' in outlook_lower or 'promising' in outlook_lower:
            return '#FFFF00'  # Yellow - good outlook
        elif 'average' in outlook_lower or 'moderate' in outlook_lower:
            return '#FFA500'  # Orange - average outlook
        elif 'poor' in outlook_lower or 'limited' in outlook_lower or 'declining' in outlook_lower:
            return '#FF6B6B'  # Red - poor outlook
        else:
            return None  # Default color
    
    def _show_player_details(self, player):
        """Show detailed development information for a player"""
        # Clear previous details
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        
        # Player header
        header_frame = ttk.Frame(self.detail_frame, style='Content.TFrame')
        header_frame.pack(fill='x', pady=(0, 20), padx=0)  # No padding - fill completely
        
        name_label = ttk.Label(header_frame, text=f"{player.full_name}", 
                              style='Title.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        name_label.pack()
        
        info_label = ttk.Label(header_frame, 
                              text=f"{player.age} years old • {player.primary_position.value}",
                              style='Content.TLabel')
        info_label.pack()
        
        # Development summary
        summary = self.dev_engine.get_player_development_summary(player)
        
        summary_frame = ttk.LabelFrame(self.detail_frame, text="Development Summary", style='Card.TLabelframe')
        summary_frame.pack(fill='x', pady=(0, 10), padx=0)  # No padding - fill completely
        
        summary_info = ttk.Frame(summary_frame, style='Content.TFrame')
        summary_info.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Configure grid to expand and fill available width
        summary_info.columnconfigure(0, weight=1)
        summary_info.columnconfigure(1, weight=1)
        summary_info.columnconfigure(2, weight=1) 
        summary_info.columnconfigure(3, weight=1)
        
        # Development stats with color coding
        dev_stats = [
            ("Development Stage", summary['development_stage'].title(), None),
            ("Current Overall", str(summary['current_overall']), None),
            ("Potential Overall", str(summary['potential_overall']), 
             self._get_overall_potential_color(summary['current_overall'], summary['potential_overall'])),
            ("Development Rate", f"{summary['base_development_rate']:+.2f}", 
             self._get_development_rate_color(summary['base_development_rate'])),
            ("Outlook", summary['development_outlook'], 
             self._get_outlook_color(summary['development_outlook']))
        ]
        
        for i, (label, value, color) in enumerate(dev_stats):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(summary_info, text=f"{label}:", style='Content.TLabel').grid(
                row=row, column=col, sticky='ew', padx=(0, 10), pady=2)
            
            # Create value label with color coding if specified
            value_label = ttk.Label(summary_info, text=value, style='Content.TLabel', 
                                  font=(self.parent.FONT_FAMILY, 10, 'bold'))
            if color:
                value_label.configure(foreground=color)
            value_label.grid(row=row, column=col+1, sticky='ew', padx=(0, 30), pady=2)
        
        # Attribute potentials
        if hasattr(player, 'potential'):
            potential_frame = ttk.LabelFrame(self.detail_frame, text="Attribute Potentials", style='Card.TLabelframe')
            potential_frame.pack(fill='x', pady=(0, 10), padx=0)  # No padding - fill completely
            
            potential_info = ttk.Frame(potential_frame, style='Content.TFrame')
            potential_info.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Configure grid columns to expand and distribute evenly
            for col in range(9):  # 3 attributes × 3 columns each
                potential_info.columnconfigure(col, weight=1)
            
            # Show key attributes and their potentials
            key_attributes = ['skating', 'shooting', 'passing', 'checking', 'defense', 'hockey_iq']
            
            for i, attr in enumerate(key_attributes):
                if hasattr(player, attr):
                    current = getattr(player, attr)
                    potential = player.potential.get_potential_for_attribute(attr)
                    
                    row = i // 3
                    col = (i % 3) * 3
                    
                    # Attribute name
                    ttk.Label(potential_info, text=f"{attr.title()}:", style='Content.TLabel').grid(
                        row=row, column=col, sticky='ew', padx=(0, 5), pady=2)
                    
                    # Current value
                    ttk.Label(potential_info, text=str(current), style='Content.TLabel').grid(
                        row=row, column=col+1, sticky='ew', padx=(0, 5), pady=2)
                    
                    # Potential with enhanced color coding
                    potential_color = self._get_potential_color(current, potential)
                    potential_label = ttk.Label(potential_info, text=f"({potential})", 
                                              style='Content.TLabel', foreground=potential_color,
                                              font=(self.parent.FONT_FAMILY, 10, 'bold'))
                    potential_label.grid(row=row, column=col+2, sticky='ew', padx=(0, 15), pady=2)
        
        # Active training
        if player.id in self.dev_engine.active_training_programs:
            training = self.dev_engine.active_training_programs[player.id]
            
            training_frame = ttk.LabelFrame(self.detail_frame, text="Active Training", style='Card.TLabelframe')
            training_frame.pack(fill='x', pady=(0, 10), padx=0)  # No padding - fill completely
            
            training_info = ttk.Frame(training_frame, style='Content.TFrame')
            training_info.pack(fill='both', expand=True, padx=10, pady=10)
            
            ttk.Label(training_info, text=f"Focus: {training.focus.value.title()}", 
                     style='Content.TLabel').pack(anchor='w')
            ttk.Label(training_info, text=f"Progress: {training.progress_percentage:.1f}%", 
                     style='Content.TLabel').pack(anchor='w')
            ttk.Label(training_info, text=f"Intensity: {training.intensity}/10", 
                     style='Content.TLabel').pack(anchor='w')
            
            # Progress bar
            progress_frame = ttk.Frame(training_info, style='Content.TFrame')
            progress_frame.pack(fill='x', pady=(5, 0))
            
            progress_bar = ttk.Progressbar(progress_frame, mode='determinate', 
                                         value=training.progress_percentage)
            progress_bar.pack(fill='x')
        
        # Force canvas to update its scroll region and item width after adding content
        self.after_idle(self._update_canvas_dimensions)
    
    def _start_training_program(self):
        """Start a new training program"""
        # Validate inputs
        if not self.training_player_var.get():
            messagebox.showerror("Error", "Please select a player")
            return
        
        if not self.training_focus_var.get():
            messagebox.showerror("Error", "Please select a training focus")
            return
        
        try:
            intensity = int(self.intensity_var.get())
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid intensity or duration")
            return
        
        # Get trainer quality from selection
        trainer_text = self.trainer_quality_var.get()
        trainer_quality = int(trainer_text.split('(')[1].split(')')[0])
        
        # Find selected player
        player_name = self.training_player_var.get().split(' (')[0]
        selected_player = None
        
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
            
            for player in all_players:
                if player.full_name == player_name:
                    selected_player = player
                    break
        
        if not selected_player:
            messagebox.showerror("Error", "Player not found")
            return
        
        # Convert focus string to enum
        focus_value = self.training_focus_var.get().lower()
        training_focus = None
        for focus in TrainingFocus:
            if focus.value == focus_value:
                training_focus = focus
                break
        
        if not training_focus:
            messagebox.showerror("Error", "Invalid training focus")
            return
        
        # Start training program
        success = self.dev_engine.start_training_program(
            selected_player, training_focus, intensity, duration, trainer_quality
        )
        
        if success:
            messagebox.showinfo("Success", f"Training program started for {player_name}")
            self._update_all_views()
        else:
            messagebox.showerror("Error", "Failed to start training program (player may already be training)")
    
    def _on_history_player_select(self, event):
        """Handle player selection for development history"""
        if not self.history_player_var.get():
            return
        
        # Find selected player
        player_name = self.history_player_var.get().split(' (')[0]
        selected_player = None
        
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
            
            for player in all_players:
                if player.full_name == player_name:
                    selected_player = player
                    break
        
        if selected_player:
            self._show_development_history(selected_player)
    
    def _show_development_history(self, player):
        """Show development history for a player"""
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Get development history
        if player.id in self.dev_engine.development_history:
            history = self.dev_engine.development_history[player.id]
            
            # Show attribute changes
            for attribute, changes in history.attribute_changes.items():
                for change_date, change_value, reason in changes:
                    # Get current value for this attribute
                    current_value = getattr(player, attribute, 0)
                    
                    values = (
                        change_date.strftime("%Y-%m-%d"),
                        attribute.title(),
                        f"{change_value:+d}",
                        reason,
                        str(current_value)
                    )
                    
                    item_id = self.history_tree.insert('', 'end', values=values)
                    
                    # Color code positive/negative changes
                    if change_value > 0:
                        self.history_tree.set(item_id, 'tags', ('positive',))
                    else:
                        self.history_tree.set(item_id, 'tags', ('negative',))
            
            # Configure tags
            self.history_tree.tag_configure('positive', foreground='green')
            self.history_tree.tag_configure('negative', foreground='red')
    
    def _process_monthly_development(self):
        """Process monthly development for all team players"""
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
        
        result = messagebox.askyesno("Process Development", 
                                   "Process monthly development for all players?\n\n"
                                   "This will apply natural development/decline based on age and potential.")
        
        if not result:
            return
        
        # Process development for all players
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        total_changes = 0
        development_summary = {}
        
        for player in all_players:
            changes = self.dev_engine.process_monthly_development(player)
            if changes:
                development_summary[player.full_name] = changes
                total_changes += len(changes)
        
        # Show summary
        if total_changes > 0:
            summary_text = f"Development processed for {len(all_players)} players.\n"
            summary_text += f"Total attribute changes: {total_changes}\n\n"
            
            # Show some specific changes
            for player_name, changes in list(development_summary.items())[:5]:
                summary_text += f"{player_name}: {', '.join(f'{attr} {change:+d}' for attr, change in changes.items())}\n"
            
            if len(development_summary) > 5:
                summary_text += f"... and {len(development_summary) - 5} more players"
            
            messagebox.showinfo("Development Complete", summary_text)
        else:
            messagebox.showinfo("Development Complete", "No significant changes this month.")
        
        # Refresh views
        self._update_all_views()
    
    def _update_all_views(self):
        """Update all views with current data"""
        self._populate_player_list()
        self._update_training_list()
        
        # Update any selected player details
        selection = self.player_tree.selection()
        if selection:
            item = selection[0]
            player = self.player_tree.set(item, 'player_obj')
            if player:
                self._show_player_details(player)
    
    def _update_training_list(self):
        """Update the active training programs list"""
        # Clear existing items
        for item in self.training_tree.get_children():
            self.training_tree.delete(item)
        
        # Check for completed programs
        completed = self.dev_engine.complete_training_programs()
        
        # Show completed program results
        if completed:
            for player_id, program in completed.items():
                # Find the player
                player = None
                if hasattr(self.parent, 'user_team') and self.parent.user_team:
                    all_players = (self.parent.user_team.roster + 
                                  self.parent.user_team.ahl_roster + 
                                  self.parent.user_team.prospects)
                    
                    for p in all_players:
                        if p.id == player_id:
                            player = p
                            break
                
                if player:
                    # Apply training effects
                    changes = self.dev_engine.apply_training_effects(player, program)
                    
                    if changes:
                        change_text = ', '.join(f'{attr} +{change}' for attr, change in changes.items())
                        messagebox.showinfo("Training Complete", 
                                          f"{player.full_name} completed {program.focus.value} training!\n\n"
                                          f"Improvements: {change_text}")
        
        # Show active programs
        for player_id, program in self.dev_engine.active_training_programs.items():
            # Find player name
            player_name = "Unknown"
            if hasattr(self.parent, 'user_team') and self.parent.user_team:
                all_players = (self.parent.user_team.roster + 
                              self.parent.user_team.ahl_roster + 
                              self.parent.user_team.prospects)
                
                for player in all_players:
                    if player.id == player_id:
                        player_name = player.full_name
                        break
            
            # Calculate estimated completion date
            weeks_remaining = program.duration_weeks - ((date.today() - program.started_date).days // 7)
            completion_date = date.today() + timedelta(weeks=weeks_remaining)
            
            values = (
                player_name,
                program.focus.value.title(),
                f"{program.intensity}/10",
                f"{program.progress_percentage:.1f}%",
                f"{program.trainer_quality}/20",
                completion_date.strftime("%Y-%m-%d")
            )
            
            self.training_tree.insert('', 'end', values=values)
    
    def _on_canvas_configure_resize(self, event):
        """Handle canvas resize to update detail frame width"""
        if hasattr(self, 'canvas_window'):
            # Force the canvas window (detail_frame) to fill the canvas width
            canvas_width = event.width
            if canvas_width > 10:  # Ensure valid width
                self.detail_canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _on_canvas_configure_frame(self):
        """Handle detail frame configure to update scroll region"""
        # Update scroll region when detail frame content changes
        self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))
    
    def _initial_canvas_setup(self):
        """Initial setup to ensure canvas and frame dimensions are correct"""
        if hasattr(self, 'detail_canvas') and hasattr(self, 'canvas_window'):
            # Force an update to get proper canvas width
            self.detail_canvas.update_idletasks()
            canvas_width = self.detail_canvas.winfo_width()
            if canvas_width > 10:
                self.detail_canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _update_canvas_dimensions(self):
        """Force update of canvas dimensions and content width"""
        if hasattr(self, 'detail_canvas') and hasattr(self, 'canvas_window'):
            # Get current canvas width and update window
            self.detail_canvas.update_idletasks()
            canvas_width = self.detail_canvas.winfo_width()
            if canvas_width > 10:  # Make sure canvas is actually displayed
                # Update the window width to match canvas exactly
                self.detail_canvas.itemconfig(self.canvas_window, width=canvas_width)
                
                # Update scroll region
                self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))

    def _on_window_resize(self, event):
        """Handle window resize to update canvas dimensions"""
        # Only handle resize events for the main window, not child widgets
        if event.widget == self:
            # Update canvas scroll region if detail frame exists
            if hasattr(self, 'detail_canvas') and hasattr(self, 'detail_frame'):
                # Schedule scroll region update after other events
                self.after_idle(lambda: self.detail_canvas.configure(
                    scrollregion=self.detail_canvas.bbox("all")
                ))
