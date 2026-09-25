"""
Professional Player Development Window - Complete Redesign
Modern, polished interface with enhanced functionality and visual design
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
from datetime import datetime, timedelta
from player_development_system import PlayerDevelopmentEngine, initialize_player_potential
from game_classes import Player, PlayerPosition, to_100_scale

class PlayerDevelopmentWindowProfessional(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Player Development Center")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        self.configure(background=parent.BG_COLOR)
        
        # Initialize development engine
        self.dev_engine = PlayerDevelopmentEngine()
        
        # Initialize tracking variables
        self._sort_reverse = {}
        self.player_data = []
        self.filtered_players = []
        self.selected_player = None
        self.search_var = tk.StringVar(master=self)
        self.position_filter = tk.StringVar(master=self, value="All Positions")
        self.age_filter = tk.StringVar(master=self, value="All Ages")
        self.potential_filter = tk.StringVar(master=self, value="All Potentials")
        
        # Initialize potentials for existing players
        self._initialize_player_potentials()
        
        # Setup professional styling
        self._setup_professional_styles()
        
        # Create the professional interface
        self._create_interface()
        self._populate_data()
        
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
                    
    def _setup_professional_styles(self):
        """Setup modern, professional styling using parent's dark theme"""
        style = ttk.Style()
        
        # Use parent's dark theme colors
        self.colors = {
            'primary': self.parent.HEADER_COLOR,      # White text
            'secondary': self.parent.TEXT_COLOR,      # Light gray text
            'accent': self.parent.ACCENT_COLOR,       # Red accent
            'success': '#27AE60',                     # Green
            'warning': '#F39C12',                     # Orange
            'danger': '#E74C3C',                      # Red
            'light': self.parent.TEXT_COLOR,          # Light text
            'dark': self.parent.BG_COLOR,             # Dark background
            'card_bg': self.parent.CONTENT_BG,        # Dark card background
            'border': '#444444'                       # Dark border
        }
        
        # Configure notebook style for tabs
        style.configure('Professional.TNotebook', 
                       background=self.parent.BG_COLOR,
                       borderwidth=0)
        style.configure('Professional.TNotebook.Tab',
                       padding=[20, 12],
                       font=('Segoe UI', 10, 'normal'),
                       borderwidth=1)
        
        # Configure card-style frames with dark theme
        style.configure('Card.TLabelframe',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR,
                       relief='flat',
                       borderwidth=1,
                       labelanchor='n')
        style.configure('Card.TLabelframe.Label',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.HEADER_COLOR,
                       font=('Segoe UI', 11, 'bold'))
                       
        # Configure search and filter frames with dark theme
        style.configure('Filter.TFrame',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR,
                       relief='flat',
                       borderwidth=1)
                       
        # Configure dark frame style
        style.configure('Dark.TFrame',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR)
                       
        # Configure dark label styles
        style.configure('Dark.TLabel',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.TEXT_COLOR,
                       font=('Segoe UI', 10))
        style.configure('DarkBold.TLabel',
                       background=self.parent.CONTENT_BG,
                       foreground=self.parent.HEADER_COLOR,
                       font=('Segoe UI', 10, 'bold'))
        style.configure('DarkTitle.TLabel',
                       background=self.parent.BG_COLOR,
                       foreground=self.parent.HEADER_COLOR,
                       font=('Segoe UI', 18, 'bold'))
                       
    def _create_interface(self):
        """Create the professional interface with tabbed layout"""
        # Main container with padding
        main_container = ttk.Frame(self)
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header section
        self._create_header(main_container)
        
        # Filters and search section
        self._create_filters_section(main_container)
        
        # Main content with tabs
        self._create_tabbed_content(main_container)
        
    def _create_header(self, parent):
        """Create professional header section"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=(0, 20))
        
        # Title and description with dark theme
        title_label = ttk.Label(header_frame, 
                               text="Player Development Center",
                               style='DarkTitle.TLabel')
        title_label.pack(anchor='w')
        
        desc_label = ttk.Label(header_frame,
                              text="Monitor player progress, assign training focus, and track development potential",
                              style='Dark.TLabel')
        desc_label.pack(anchor='w', pady=(5, 0))
        
        # Quick stats
        stats_frame = ttk.Frame(header_frame)
        stats_frame.pack(anchor='w', pady=(10, 0))
        
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
            
            # Calculate quick stats
            total_players = len(all_players)
            prospects = len([p for p in all_players if p.age <= 23])
            high_potential = len([p for p in all_players if hasattr(p, 'potential') and p.potential >= 16])
            
            self._create_stat_card(stats_frame, "Total Players", str(total_players), self.colors['primary'])
            self._create_stat_card(stats_frame, "Prospects (≤23)", str(prospects), self.colors['accent'])
            self._create_stat_card(stats_frame, "High Potential", str(high_potential), self.colors['success'])
    
    def _create_stat_card(self, parent, title, value, color):
        """Create a small stat card with dark theme"""
        card = ttk.Frame(parent, style='Filter.TFrame')
        card.pack(side='left', padx=(0, 15), pady=5, ipadx=15, ipady=10)
        
        value_label = ttk.Label(card, text=value, 
                               font=('Segoe UI', 16, 'bold'),
                               foreground=color,
                               background=self.parent.CONTENT_BG)
        value_label.pack()
        
        title_label = ttk.Label(card, text=title,
                               font=('Segoe UI', 9),
                               foreground=self.parent.TEXT_COLOR,
                               background=self.parent.CONTENT_BG)
        title_label.pack()
    
    def _create_filters_section(self, parent):
        """Create filters and search section"""
        filter_frame = ttk.LabelFrame(parent, text="Filters & Search", style='Card.TLabelframe')
        filter_frame.pack(fill='x', pady=(0, 15))
        
        # Inner container for proper padding with dark theme
        filter_container = ttk.Frame(filter_frame, style='Dark.TFrame')
        filter_container.pack(fill='x', padx=20, pady=15)
        
        # Search section
        search_frame = ttk.Frame(filter_container)
        search_frame.pack(side='left', fill='x', expand=True)
        
        search_label = ttk.Label(search_frame, text="Search Players:", 
                               font=('Segoe UI', 10, 'bold'))
        search_label.configure(foreground=self.parent.HEADER_COLOR, background=self.parent.CONTENT_BG)
        search_label.pack(anchor='w')
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30,
                                font=('Segoe UI', 10))
        search_entry.pack(anchor='w', pady=(5, 0))
        search_entry.bind('<KeyRelease>', lambda e: self._apply_filters())
        
        # Filter dropdowns
        filters_frame = ttk.Frame(filter_container)
        filters_frame.pack(side='right', padx=(20, 0))
        
        # Position filter with dark theme
        pos_frame = ttk.Frame(filters_frame, style='Dark.TFrame')
        pos_frame.pack(side='left', padx=(0, 15))
        pos_label = ttk.Label(pos_frame, text="Position:", style='DarkBold.TLabel')
        pos_label.pack()
        pos_combo = ttk.Combobox(pos_frame, textvariable=self.position_filter, width=12,
                                values=["All Positions", "Center", "Left Wing", "Right Wing", 
                                       "Defense", "Goalie"], state='readonly')
        pos_combo.pack(pady=(5, 0))
        pos_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())
        
        # Age filter with dark theme
        age_frame = ttk.Frame(filters_frame, style='Dark.TFrame')
        age_frame.pack(side='left', padx=(0, 15))
        age_label = ttk.Label(age_frame, text="Age:", style='DarkBold.TLabel')
        age_label.pack()
        age_combo = ttk.Combobox(age_frame, textvariable=self.age_filter, width=12,
                                values=["All Ages", "18-20", "21-23", "24-26", "27-30", "30+"],
                                state='readonly')
        age_combo.pack(pady=(5, 0))
        age_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())
        
        # Potential filter with dark theme
        pot_frame = ttk.Frame(filters_frame, style='Dark.TFrame')
        pot_frame.pack(side='left')
        pot_label = ttk.Label(pot_frame, text="Potential:", style='DarkBold.TLabel')
        pot_label.pack()
        pot_combo = ttk.Combobox(pot_frame, textvariable=self.potential_filter, width=12,
                                values=["All Potentials", "A+ (18-20)", "A (16-17)", "B (14-15)", 
                                       "C (12-13)", "D+ (10-11)"], state='readonly')
        pot_combo.pack(pady=(5, 0))
        pot_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())
        
    def _create_tabbed_content(self, parent):
        """Create main content area with professional tabs"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent, style='Professional.TNotebook')
        self.notebook.pack(fill='both', expand=True)
        
        # Overview tab
        self._create_overview_tab()
        
        # Individual Development tab
        self._create_individual_tab()
        
        # Team Analysis tab
        self._create_analysis_tab()
        
    def _create_overview_tab(self):
        """Create the overview tab with player list and quick details"""
        overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(overview_frame, text="📊 Overview")
        
        # Create paned window for resizable layout
        paned = ttk.PanedWindow(overview_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Player list
        left_frame = ttk.LabelFrame(paned, text="Team Players", style='Card.TLabelframe')
        paned.add(left_frame, weight=2)
        
        # Player list with professional styling
        list_container = ttk.Frame(left_frame)
        list_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Column definitions with better headers
        columns = {
            'name': ('Player', 180),
            'pos': ('Pos', 50),
            'age': ('Age', 50),
            'overall': ('OVR', 50),
            'potential': ('POT', 50),
            'potential_grade': ('Grade', 60),
            'development_stage': ('Stage', 100),
            'focus_area': ('Focus', 120)
        }
        
        # Create treeview with professional styling
        self.player_tree = ttk.Treeview(list_container, 
                                       columns=list(columns.keys()),
                                       show='headings',
                                       height=20)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            self.player_tree.heading(col_id, text=header, anchor='center',
                                   command=lambda c=col_id: self._sort_by_column(c))
            self.player_tree.column(col_id, width=width, anchor='center', minwidth=50)
        
        # Professional scrollbars
        v_scrollbar = ttk.Scrollbar(list_container, orient='vertical', 
                                   command=self.player_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_container, orient='horizontal',
                                   command=self.player_tree.xview)
        self.player_tree.configure(yscrollcommand=v_scrollbar.set,
                                  xscrollcommand=h_scrollbar.set)
        
        # Grid layout for scrollbars
        self.player_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        # Bind selection and right-click events
        self.player_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        self.player_tree.bind('<Button-3>', self._show_player_context_menu)  # Right-click
        
        # Right side - Player details
        right_frame = ttk.LabelFrame(paned, text="Player Details", style='Card.TLabelframe')
        paned.add(right_frame, weight=1)
        
        # Details container with scrolling
        details_container = ttk.Frame(right_frame)
        details_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Create scrollable frame for details with dark theme
        self.details_canvas = tk.Canvas(details_container, bg=self.parent.CONTENT_BG, highlightthickness=0)
        details_scrollbar = ttk.Scrollbar(details_container, orient='vertical',
                                        command=self.details_canvas.yview)
        self.scrollable_details = ttk.Frame(self.details_canvas)
        
        self.scrollable_details.bind('<Configure>',
                                   lambda e: self.details_canvas.configure(
                                       scrollregion=self.details_canvas.bbox('all')))
        
        self.details_canvas.create_window((0, 0), window=self.scrollable_details, anchor='nw')
        self.details_canvas.configure(yscrollcommand=details_scrollbar.set)
        
        self.details_canvas.pack(side='left', fill='both', expand=True)
        details_scrollbar.pack(side='right', fill='y')
        
        # Initial details content
        self._create_player_details_content()
        
        # Configure grade colors
        self._configure_grade_colors()
        
    def _create_individual_tab(self):
        """Create individual player development tab"""
        individual_frame = ttk.Frame(self.notebook)
        self.notebook.add(individual_frame, text="👤 Individual Development")
        
        # Create paned window
        individual_paned = ttk.PanedWindow(individual_frame, orient='horizontal')
        individual_paned.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Player selection for training
        training_selection_frame = ttk.LabelFrame(individual_paned, 
                                                 text="Training Assignment", 
                                                 style='Card.TLabelframe')
        individual_paned.add(training_selection_frame, weight=1)
        
        selection_content = ttk.Frame(training_selection_frame)
        selection_content.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Player selection
        ttk.Label(selection_content, text="Select Player:", 
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        
        self.training_player_var = tk.StringVar(master=self)
        self.training_player_combo = ttk.Combobox(selection_content, 
                                                 textvariable=self.training_player_var,
                                                 state='readonly', width=30)
        self.training_player_combo.pack(anchor='w', pady=(5, 15), fill='x')
        self.training_player_combo.bind('<<ComboboxSelected>>', self._on_training_player_select)
        
        # Training focus selection
        ttk.Label(selection_content, text="Training Focus:", 
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(10, 5))
        
        self.training_focuses = [
            "Skating & Speed", "Shooting Accuracy", "Passing & Vision", 
            "Defensive Positioning", "Physical Conditioning", "Mental Toughness",
            "Position-Specific Skills", "Hockey IQ Development"
        ]
        
        self.focus_var = tk.StringVar(master=self)
        for focus in self.training_focuses:
            rb = ttk.Radiobutton(selection_content, text=focus, 
                               variable=self.focus_var, value=focus)
            rb.pack(anchor='w', pady=2)
        
        # Training intensity
        ttk.Label(selection_content, text="Training Intensity:", 
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(15, 5))
        
        self.intensity_var = tk.StringVar(master=self, value="Standard")
        intensity_frame = ttk.Frame(selection_content)
        intensity_frame.pack(anchor='w', pady=(5, 15))
        
        for intensity in ["Light", "Standard", "Intensive"]:
            rb = ttk.Radiobutton(intensity_frame, text=intensity,
                               variable=self.intensity_var, value=intensity)
            rb.pack(side='left', padx=(0, 15))
        
        # Assign button
        assign_btn = ttk.Button(selection_content, text="📋 Assign Training Program",
                               command=self._assign_training)
        assign_btn.pack(pady=(20, 10), fill='x')
        
        # Right side - Training progress and history
        progress_frame = ttk.LabelFrame(individual_paned, 
                                       text="Progress Tracking", 
                                       style='Card.TLabelframe')
        individual_paned.add(progress_frame, weight=1)
        
        progress_content = ttk.Frame(progress_frame)
        progress_content.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Progress display area
        self.progress_display = ttk.Frame(progress_content)
        self.progress_display.pack(fill='both', expand=True)
        
        self._update_training_players()
        self._update_progress_display()
        
    def _create_analysis_tab(self):
        """Create team analysis tab"""
        analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(analysis_frame, text="📈 Team Analysis")
        
        # Scrollable frame for analytics with dark theme
        analysis_canvas = tk.Canvas(analysis_frame, bg=self.parent.BG_COLOR, highlightthickness=0)
        analysis_scrollbar = ttk.Scrollbar(analysis_frame, orient='vertical',
                                         command=analysis_canvas.yview)
        self.scrollable_analysis = ttk.Frame(analysis_canvas)
        
        self.scrollable_analysis.bind('<Configure>',
                                    lambda e: analysis_canvas.configure(
                                        scrollregion=analysis_canvas.bbox('all')))
        
        analysis_canvas.create_window((0, 0), window=self.scrollable_analysis, anchor='nw')
        analysis_canvas.configure(yscrollcommand=analysis_scrollbar.set)
        
        analysis_canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        analysis_scrollbar.pack(side='right', fill='y', pady=10)
        
        # Team overview analytics
        self._create_team_overview_analytics()
        
        # Position analysis
        self._create_position_analysis()
        
        # Age distribution
        self._create_age_analysis()
        
        # Development pipeline
        self._create_pipeline_analysis()
        
    def _create_player_details_content(self):
        """Create the detailed player information panel"""
        # Clear existing content
        for widget in self.scrollable_details.winfo_children():
            widget.destroy()
            
        if not self.selected_player:
            # No player selected message
            no_selection_frame = ttk.Frame(self.scrollable_details)
            no_selection_frame.pack(fill='both', expand=True, pady=50)
            
            ttk.Label(no_selection_frame,
                     text="Select a player to view details",
                     font=('Segoe UI', 12),
                     foreground=self.colors['secondary']).pack()
            return
            
        player = self.selected_player
        
        # Player header
        header_frame = ttk.Frame(self.scrollable_details)
        header_frame.pack(fill='x', pady=(0, 20))
        
        name_label = ttk.Label(header_frame,
                              text=player.full_name,
                              font=('Segoe UI', 14, 'bold'),
                              foreground=self.colors['primary'])
        name_label.pack(anchor='w')
        
        # Make player name clickable with right-click context menu
        name_label.bind('<Button-3>', lambda e: self._show_details_context_menu(e, player))
        
        info_text = f"{player.primary_position.value} • Age {player.age} • {player.overall_rating()} OVR"
        info_label = ttk.Label(header_frame,
                              text=info_text,
                              font=('Segoe UI', 10),
                              foreground=self.colors['secondary'])
        info_label.pack(anchor='w')
        
        # Development summary card
        self._create_development_summary_card(player)
        
        # Attributes breakdown
        self._create_attributes_breakdown(player)
        
        # Development recommendations
        self._create_development_recommendations(player)
        
    def _create_development_summary_card(self, player):
        """Create development summary card"""
        summary_frame = ttk.LabelFrame(self.scrollable_details, 
                                     text="Development Summary", 
                                     style='Card.TLabelframe')
        summary_frame.pack(fill='x', pady=(0, 15))
        
        summary_content = ttk.Frame(summary_frame)
        summary_content.pack(fill='x', padx=15, pady=10)
        
        try:
            summary = self.dev_engine.get_player_development_summary(player)
            
            # Current vs Potential
            current_pot_frame = ttk.Frame(summary_content)
            current_pot_frame.pack(fill='x', pady=(0, 10))
            
            current_label = ttk.Label(current_pot_frame,
                                    text=f"Current Rating: {to_100_scale(player.overall_rating())}",
                                    font=('Segoe UI', 11, 'bold'))
            current_label.pack(side='left')
            
            pot_rating = self.dev_engine.calculate_potential_overall(player)
            potential_label = ttk.Label(current_pot_frame,
                                      text=f"Potential: {pot_rating}",
                                      font=('Segoe UI', 11, 'bold'),
                                      foreground=self.colors['success'])
            potential_label.pack(side='right')
            
            # Progress bar
            progress_frame = ttk.Frame(summary_content)
            progress_frame.pack(fill='x', pady=(0, 10))
            
            progress = (player.overall_rating() / pot_rating) * 100 if pot_rating > 0 else 0
            progress_bar = ttk.Progressbar(progress_frame, length=200, mode='determinate')
            progress_bar['value'] = progress
            progress_bar.pack(side='left', fill='x', expand=True)
            
            progress_label = ttk.Label(progress_frame, text=f"{progress:.1f}%")
            progress_label.pack(side='right', padx=(10, 0))
            
            # Development stage and outlook
            stage_text = summary.get('development_stage', 'Unknown')
            outlook_text = summary.get('outlook', 'No outlook available')
            
            ttk.Label(summary_content, 
                     text=f"Development Stage: {stage_text}",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(5, 0))
            
            ttk.Label(summary_content,
                     text=outlook_text,
                     font=('Segoe UI', 10),
                     foreground=self.colors['secondary'],
                     wraplength=250).pack(anchor='w', pady=(5, 0))
            
        except Exception as e:
            error_label = ttk.Label(summary_content,
                                   text="Development data unavailable",
                                   font=('Segoe UI', 10),
                                   foreground=self.colors['danger'])
            error_label.pack()
            
    def _create_attributes_breakdown(self, player):
        """Create detailed attributes breakdown"""
        attr_frame = ttk.LabelFrame(self.scrollable_details,
                                   text="Key Attributes",
                                   style='Card.TLabelframe')
        attr_frame.pack(fill='x', pady=(0, 15))
        
        attr_content = ttk.Frame(attr_frame)
        attr_content.pack(fill='both', padx=15, pady=10)
        
        # Key attributes based on position
        key_attrs = self._get_key_attributes_for_position(player.primary_position)
        
        for i, attr in enumerate(key_attrs[:6]):  # Limit to 6 attributes
            attr_row = ttk.Frame(attr_content)
            attr_row.pack(fill='x', pady=2)
            
            attr_name = attr.replace('_', ' ').title()
            current_val = getattr(player, attr, 10)
            
            # Attribute name
            name_label = ttk.Label(attr_row, text=attr_name, width=15, anchor='w')
            name_label.pack(side='left')
            
            # Progress bar for attribute
            attr_progress = ttk.Progressbar(attr_row, length=100, mode='determinate')
            attr_progress['value'] = (current_val / 20) * 100
            attr_progress.pack(side='left', padx=(10, 5))
            
            # Value label
            val_label = ttk.Label(attr_row, text=str(current_val), width=3)
            val_label.pack(side='left')
            
            # Grade
            grade = self._get_attribute_grade(current_val)
            grade_label = ttk.Label(attr_row, text=grade, width=4,
                                   foreground=self._get_grade_color(grade))
            grade_label.pack(side='right')
    
    def _create_development_recommendations(self, player):
        """Create development recommendations"""
        rec_frame = ttk.LabelFrame(self.scrollable_details,
                                  text="Development Focus Recommendations",
                                  style='Card.TLabelframe')
        rec_frame.pack(fill='x', pady=(0, 15))
        
        rec_content = ttk.Frame(rec_frame)
        rec_content.pack(fill='both', padx=15, pady=10)
        
        # Get recommended focus areas
        recommendations = self._generate_recommendations(player)
        
        for i, (area, reason) in enumerate(recommendations[:3]):  # Top 3 recommendations
            rec_item = ttk.Frame(rec_content)
            rec_item.pack(fill='x', pady=5)
            
            # Priority indicator
            priority_colors = [self.colors['success'], self.colors['warning'], self.colors['accent']]
            priority_labels = ['HIGH', 'MED', 'LOW']
            
            priority_label = ttk.Label(rec_item,
                                     text=priority_labels[i],
                                     font=('Segoe UI', 8, 'bold'),
                                     foreground=priority_colors[i],
                                     width=5)
            priority_label.pack(side='left')
            
            # Recommendation text
            rec_text = f"{area}: {reason}"
            rec_label = ttk.Label(rec_item,
                                 text=rec_text,
                                 font=('Segoe UI', 9),
                                 wraplength=200,
                                 justify='left')
            rec_label.pack(side='left', padx=(10, 0), fill='x', expand=True)
            
    def _get_key_attributes_for_position(self, position):
        """Get key attributes for a player's position"""
        position_attrs = {
            PlayerPosition.CENTER: ['skating', 'passing', 'faceoffs', 'hockey_iq', 'vision', 'determination'],
            PlayerPosition.LEFT_WING: ['skating', 'shooting', 'passing', 'checking', 'determination', 'conditioning'],
            PlayerPosition.RIGHT_WING: ['skating', 'shooting', 'passing', 'checking', 'determination', 'conditioning'],
            PlayerPosition.DEFENSE: ['skating', 'defense', 'passing', 'checking', 'positioning', 'hockey_iq'],
            PlayerPosition.GOALIE: ['goaltending', 'reflexes', 'positioning', 'rebound_control', 'mental_toughness', 'consistency']
        }
        
        return position_attrs.get(position, ['skating', 'shooting', 'passing', 'defense', 'hockey_iq', 'determination'])
    
    def _generate_recommendations(self, player):
        """Generate development recommendations for a player"""
        recommendations = []
        
        # Get key attributes and find weaknesses
        key_attrs = self._get_key_attributes_for_position(player.primary_position)
        
        attr_values = [(attr, getattr(player, attr, 10)) for attr in key_attrs]
        attr_values.sort(key=lambda x: x[1])  # Sort by value, lowest first
        
        # Recommend improvement for lowest attributes
        if attr_values:
            lowest_attr, lowest_val = attr_values[0]
            if lowest_val < 14:
                recommendations.append((
                    lowest_attr.replace('_', ' ').title(),
                    f"Currently {lowest_val}/20 - below team standard"
                ))
        
        # Age-based recommendations
        if player.age <= 20:
            recommendations.append((
                "Intensive Training",
                "Young age allows for rapid development"
            ))
        elif player.age >= 30:
            recommendations.append((
                "Maintenance Focus",
                "Prevent attribute decline due to age"
            ))
        
        # Position-specific recommendations
        if player.primary_position == PlayerPosition.GOALIE:
            if getattr(player, 'mental_toughness', 10) < 15:
                recommendations.append((
                    "Mental Training",
                    "Critical for goalie consistency"
                ))
        
        return recommendations[:3]  # Return top 3
    
    def _get_attribute_grade(self, value):
        """Convert attribute value to letter grade"""
        if value >= 18: return 'A+'
        elif value >= 16: return 'A'
        elif value >= 14: return 'B+'
        elif value >= 12: return 'B'
        elif value >= 10: return 'C+'
        elif value >= 8: return 'C'
        else: return 'D'
    
    def _get_grade_color(self, grade):
        """Get color for grade"""
        grade_colors = {
            'A+': self.colors['success'],
            'A': '#2ECC71',
            'B+': self.colors['accent'],
            'B': '#3498DB',
            'C+': self.colors['warning'],
            'C': '#F39C12',
            'D': self.colors['danger']
        }
        return grade_colors.get(grade, self.colors['secondary'])
    
    def _configure_grade_colors(self):
        """Configure colors for potential grades in treeview"""
        grade_colors = {
            'A+': '#27AE60',  # Green
            'A': '#2ECC71',   # Light green
            'B+': '#3498DB',  # Blue
            'B': '#5DADE2',   # Light blue
            'C+': '#F39C12',  # Orange
            'C': '#F8C471',   # Light orange
            'D+': '#E74C3C',  # Red
            'D': '#EC7063'    # Light red
        }
        
        for grade, color in grade_colors.items():
            self.player_tree.tag_configure(f'grade_{grade}', foreground=color, font=('Segoe UI', 9, 'bold'))
    
    def _populate_data(self):
        """Populate the player data and apply filters"""
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        # Get all players
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Store player data
        self.player_data = []
        for player in all_players:
            try:
                summary = self.dev_engine.get_player_development_summary(player)
                pot_grade = self._get_potential_grade(player.potential if hasattr(player, 'potential') else 10)
                
                self.player_data.append({
                    'player': player,
                    'name': player.full_name,
                    'pos': player.primary_position.value,
                    'age': player.age,
                    'overall': player.overall_rating(),
                    'potential': getattr(player, 'potential', 10),
                    'potential_grade': pot_grade,
                    'development_stage': summary.get('development_stage', 'Unknown'),
                    'focus_area': 'Not Assigned'  # Will be enhanced later
                })
            except Exception as e:
                # Fallback data if summary fails
                self.player_data.append({
                    'player': player,
                    'name': player.full_name,
                    'pos': player.primary_position.value,
                    'age': player.age,
                    'overall': player.overall_rating(),
                    'potential': getattr(player, 'potential', 10),
                    'potential_grade': 'C',
                    'development_stage': 'Unknown',
                    'focus_area': 'Not Assigned'
                })
        
        # Apply filters
        self._apply_filters()
    
    def _get_potential_grade(self, potential_value):
        """Convert potential value to letter grade"""
        if potential_value >= 19: return 'A+'
        elif potential_value >= 17: return 'A'
        elif potential_value >= 15: return 'B+'
        elif potential_value >= 13: return 'B'
        elif potential_value >= 11: return 'C+'
        elif potential_value >= 9: return 'C'
        else: return 'D+'
    
    def _apply_filters(self):
        """Apply current filters to the player list"""
        filtered = []
        
        search_term = self.search_var.get().lower()
        pos_filter = self.position_filter.get()
        age_filter = self.age_filter.get()
        pot_filter = self.potential_filter.get()
        
        for player_data in self.player_data:
            # Search filter
            if search_term and search_term not in player_data['name'].lower():
                continue
                
            # Position filter
            if pos_filter != "All Positions" and player_data['pos'] != pos_filter:
                continue
                
            # Age filter
            if age_filter != "All Ages":
                age = player_data['age']
                if age_filter == "18-20" and not (18 <= age <= 20):
                    continue
                elif age_filter == "21-23" and not (21 <= age <= 23):
                    continue
                elif age_filter == "24-26" and not (24 <= age <= 26):
                    continue
                elif age_filter == "27-30" and not (27 <= age <= 30):
                    continue
                elif age_filter == "30+" and age < 30:
                    continue
                    
            # Potential filter
            if pot_filter != "All Potentials":
                pot = player_data['potential']
                if pot_filter == "A+ (18-20)" and not (18 <= pot <= 20):
                    continue
                elif pot_filter == "A (16-17)" and not (16 <= pot <= 17):
                    continue
                elif pot_filter == "B (14-15)" and not (14 <= pot <= 15):
                    continue
                elif pot_filter == "C (12-13)" and not (12 <= pot <= 13):
                    continue
                elif pot_filter == "D+ (10-11)" and not (10 <= pot <= 11):
                    continue
                    
            filtered.append(player_data)
        
        self.filtered_players = filtered
        self._update_player_tree()
    
    def _update_player_tree(self):
        """Update the player tree with filtered data"""
        # Clear existing items
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        
        # Add filtered players
        for player_data in self.filtered_players:
            values = (
                player_data['name'],
                player_data['pos'],
                player_data['age'],
                player_data['overall'],
                player_data['potential'],
                player_data['potential_grade'],
                player_data['development_stage'],
                player_data['focus_area']
            )
            
            item = self.player_tree.insert('', 'end', values=values)
            
            # Apply grade coloring
            grade = player_data['potential_grade']
            self.player_tree.item(item, tags=[f'grade_{grade}'])
    
    def _sort_by_column(self, col):
        """Sort the tree by the specified column with proper handling for all data types"""
        if col not in self._sort_reverse:
            self._sort_reverse[col] = False
        
        reverse = self._sort_reverse[col]
        
        # Sort the filtered data based on column type
        if col == 'name':
            self.filtered_players.sort(key=lambda x: x['name'].lower(), reverse=reverse)
        elif col == 'pos':
            # Sort positions in logical order: C, LW, RW, D, G
            pos_order = {'Center': 1, 'Left Wing': 2, 'Right Wing': 3, 'Defense': 4, 'Goalie': 5}
            self.filtered_players.sort(key=lambda x: pos_order.get(x['pos'], 6), reverse=reverse)
        elif col in ['age', 'overall', 'potential']:
            self.filtered_players.sort(key=lambda x: x[col], reverse=reverse)
        elif col == 'potential_grade':
            # Sort grades: A+, A, B+, B, C+, C, D+, D
            grade_order = {'A+': 8, 'A': 7, 'B+': 6, 'B': 5, 'C+': 4, 'C': 3, 'D+': 2, 'D': 1}
            self.filtered_players.sort(key=lambda x: grade_order.get(x['potential_grade'], 0), reverse=reverse)
        elif col == 'development_stage':
            # Sort development stages in logical order
            stage_order = {
                'Elite Prospect': 5, 'High Potential': 4, 'Developing': 3, 
                'Established': 2, 'Veteran': 1, 'Unknown': 0
            }
            self.filtered_players.sort(key=lambda x: stage_order.get(x['development_stage'], 0), reverse=reverse)
        elif col == 'focus_area':
            self.filtered_players.sort(key=lambda x: x['focus_area'].lower(), reverse=reverse)
        
        # Toggle sort direction for next time
        self._sort_reverse[col] = not reverse
        
        # Update the tree
        self._update_player_tree()
    
    def _on_player_select(self, event):
        """Handle player selection"""
        selection = self.player_tree.selection()
        if selection:
            item = selection[0]
            player_name = self.player_tree.item(item)['values'][0]
            
            # Find the selected player
            for player_data in self.filtered_players:
                if player_data['name'] == player_name:
                    self.selected_player = player_data['player']
                    self._create_player_details_content()
                    break
    
    def _update_training_players(self):
        """Update the training player combobox"""
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        player_names = [f"{p.full_name} ({p.primary_position.value}, {p.age})" for p in all_players]
        self.training_player_combo['values'] = player_names
        
    def _on_training_player_select(self, event):
        """Handle training player selection"""
        self._update_progress_display()
        
    def _assign_training(self):
        """Assign training program to selected player"""
        if not self.training_player_var.get():
            messagebox.showwarning("No Player Selected", 
                                 "Please select a player for training assignment.")
            return
            
        if not self.focus_var.get():
            messagebox.showwarning("No Focus Selected",
                                 "Please select a training focus area.")
            return
            
        # Extract player name from combobox selection
        selection = self.training_player_var.get()
        player_name = selection.split(" (")[0]
        
        # Show confirmation
        message = (f"Training Assignment:\n\n"
                  f"Player: {player_name}\n"
                  f"Focus: {self.focus_var.get()}\n"
                  f"Intensity: {self.intensity_var.get()}\n\n"
                  f"This training program will be active for the next 30 days.")
        
        result = messagebox.askyesno("Confirm Training Assignment", message)
        if result:
            messagebox.showinfo("Training Assigned", 
                              f"{player_name} has been assigned to {self.focus_var.get()} training.")
            self._update_progress_display()
    
    def _update_progress_display(self):
        """Update the progress display area"""
        # Clear existing content
        for widget in self.progress_display.winfo_children():
            widget.destroy()
            
        if not self.training_player_var.get():
            ttk.Label(self.progress_display,
                     text="Select a player to view training progress",
                     font=('Segoe UI', 11),
                     foreground=self.colors['secondary']).pack(pady=50)
            return
            
        # Mock training progress display
        ttk.Label(self.progress_display,
                 text="Current Training Status",
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(0, 10))
                 
        status_text = "No active training program"
        ttk.Label(self.progress_display,
                 text=status_text,
                 font=('Segoe UI', 10)).pack(anchor='w')
                 
        # Training history section
        ttk.Label(self.progress_display,
                 text="Training History",
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(20, 10))
                 
        history_text = "No previous training records available"
        ttk.Label(self.progress_display,
                 text=history_text,
                 font=('Segoe UI', 10)).pack(anchor='w')
    
    def _create_team_overview_analytics(self):
        """Create team overview analytics section"""
        overview_frame = ttk.LabelFrame(self.scrollable_analysis,
                                       text="Team Development Overview",
                                       style='Card.TLabelframe')
        overview_frame.pack(fill='x', pady=(0, 15))
        
        overview_content = ttk.Frame(overview_frame)
        overview_content.pack(fill='x', padx=15, pady=15)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Calculate analytics
        total_players = len(all_players)
        avg_age = sum(p.age for p in all_players) / total_players if total_players > 0 else 0
        avg_overall = sum(p.overall_rating() for p in all_players) / total_players if total_players > 0 else 0
        avg_potential = sum(getattr(p, 'potential', 10) for p in all_players) / total_players if total_players > 0 else 0
        
        # Display metrics
        metrics = [
            ("Total Players", f"{total_players}"),
            ("Average Age", f"{avg_age:.1f}"),
            ("Average Overall", f"{avg_overall:.1f}"),
            ("Average Potential", f"{avg_potential:.1f}")
        ]
        
        metrics_frame = ttk.Frame(overview_content)
        metrics_frame.pack(fill='x')
        
        for i, (label, value) in enumerate(metrics):
            metric_frame = ttk.Frame(metrics_frame)
            metric_frame.pack(side='left', padx=(0, 20), fill='y')
            
            ttk.Label(metric_frame, text=value,
                     font=('Segoe UI', 14, 'bold'),
                     foreground=self.colors['accent']).pack()
            ttk.Label(metric_frame, text=label,
                     font=('Segoe UI', 9)).pack()
    
    def _create_position_analysis(self):
        """Create position-based analysis"""
        pos_frame = ttk.LabelFrame(self.scrollable_analysis,
                                  text="Position Analysis",
                                  style='Card.TLabelframe')
        pos_frame.pack(fill='x', pady=(0, 15))
        
        pos_content = ttk.Frame(pos_frame)
        pos_content.pack(fill='x', padx=15, pady=15)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Group by position
        pos_groups = {}
        for player in all_players:
            pos = player.primary_position.value
            if pos not in pos_groups:
                pos_groups[pos] = []
            pos_groups[pos].append(player)
        
        # Display position stats
        for pos, players in pos_groups.items():
            pos_row = ttk.Frame(pos_content)
            pos_row.pack(fill='x', pady=5)
            
            avg_rating = sum(p.overall_rating() for p in players) / len(players)
            avg_potential = sum(getattr(p, 'potential', 10) for p in players) / len(players)
            
            ttk.Label(pos_row, text=f"{pos}:", width=12, anchor='w',
                     font=('Segoe UI', 10, 'bold')).pack(side='left')
            ttk.Label(pos_row, text=f"{len(players)} players",
                     width=12, anchor='w').pack(side='left')
            ttk.Label(pos_row, text=f"Avg: {avg_rating:.1f}",
                     width=12, anchor='w').pack(side='left')
            ttk.Label(pos_row, text=f"Pot: {avg_potential:.1f}",
                     width=12, anchor='w').pack(side='left')
    
    def _create_age_analysis(self):
        """Create age distribution analysis"""
        age_frame = ttk.LabelFrame(self.scrollable_analysis,
                                  text="Age Distribution",
                                  style='Card.TLabelframe')
        age_frame.pack(fill='x', pady=(0, 15))
        
        age_content = ttk.Frame(age_frame)
        age_content.pack(fill='x', padx=15, pady=15)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Age groups
        age_groups = {
            "18-20": len([p for p in all_players if 18 <= p.age <= 20]),
            "21-23": len([p for p in all_players if 21 <= p.age <= 23]),
            "24-26": len([p for p in all_players if 24 <= p.age <= 26]),
            "27-30": len([p for p in all_players if 27 <= p.age <= 30]),
            "30+": len([p for p in all_players if p.age > 30])
        }
        
        for age_range, count in age_groups.items():
            age_row = ttk.Frame(age_content)
            age_row.pack(fill='x', pady=2)
            
            ttk.Label(age_row, text=f"Ages {age_range}:",
                     width=15, anchor='w').pack(side='left')
            
            # Progress bar for visual representation
            progress = ttk.Progressbar(age_row, length=150, mode='determinate')
            progress['value'] = (count / len(all_players)) * 100 if all_players else 0
            progress.pack(side='left', padx=(10, 10))
            
            ttk.Label(age_row, text=f"{count} players").pack(side='left')
    
    def _create_pipeline_analysis(self):
        """Create development pipeline analysis"""
        pipeline_frame = ttk.LabelFrame(self.scrollable_analysis,
                                       text="Development Pipeline",
                                       style='Card.TLabelframe')
        pipeline_frame.pack(fill='x', pady=(0, 15))
        
        pipeline_content = ttk.Frame(pipeline_frame)
        pipeline_content.pack(fill='x', padx=15, pady=15)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
            
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        # Pipeline categories
        categories = {
            "Elite Prospects (A+ Potential)": len([p for p in all_players 
                                                  if getattr(p, 'potential', 0) >= 18 and p.age <= 23]),
            "Solid Prospects (A Potential)": len([p for p in all_players 
                                                 if 16 <= getattr(p, 'potential', 0) < 18 and p.age <= 23]),
            "Developing Players (B Potential)": len([p for p in all_players 
                                                   if 14 <= getattr(p, 'potential', 0) < 16 and p.age <= 25]),
            "Veteran Contributors": len([p for p in all_players if p.age > 25 and p.overall_rating() >= 14]),
            "Needs Development": len([p for p in all_players if p.overall_rating() < 12])
        }
        
        for category, count in categories.items():
            cat_row = ttk.Frame(pipeline_content)
            cat_row.pack(fill='x', pady=5)
            
            ttk.Label(cat_row, text=f"{category}:",
                     width=25, anchor='w',
                     font=('Segoe UI', 9, 'bold')).pack(side='left')
            ttk.Label(cat_row, text=f"{count} players",
                     foreground=self.colors['accent']).pack(side='left')

    def update_views(self):
        """Update all views with current data"""
        self._populate_data()
        if hasattr(self, 'details_canvas'):
            self._create_player_details_content()
        if hasattr(self, 'training_player_combo'):
            self._update_training_players()
        if hasattr(self, 'scrollable_analysis'):
            # Refresh analytics
            for widget in self.scrollable_analysis.winfo_children():
                widget.destroy()
            self._create_team_overview_analytics()
            self._create_position_analysis()
            self._create_age_analysis()
            self._create_pipeline_analysis()
    
    def _show_player_context_menu(self, event):
        """Show context menu for right-clicked player"""
        # Identify the clicked item
        item = self.player_tree.identify_row(event.y)
        if not item:
            return
            
        # Select the item
        self.player_tree.selection_set(item)
        
        # Get player data
        player_name = self.player_tree.item(item)['values'][0]
        selected_player = None
        
        for player_data in self.filtered_players:
            if player_data['name'] == player_name:
                selected_player = player_data['player']
                break
                
        if not selected_player:
            return
            
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.configure(bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR,
                             activebackground=self.parent.ACCENT_COLOR,
                             activeforeground='white',
                             font=('Segoe UI', 9))
        
        # Menu options
        context_menu.add_command(
            label=f"👤 View {selected_player.full_name}'s Profile",
            command=lambda: self._view_player_profile(selected_player)
        )
        
        context_menu.add_separator()
        
        context_menu.add_command(
            label="🔍 Scout Player",
            command=lambda: self._scout_player(selected_player)
        )
        
        context_menu.add_command(
            label="⭐ Add to Shortlist",
            command=lambda: self._add_to_shortlist(selected_player)
        )
        
        context_menu.add_command(
            label="📊 Compare with Another Player",
            command=lambda: self._compare_players(selected_player)
        )
        
        context_menu.add_separator()
        
        context_menu.add_command(
            label="🎯 Assign Training Focus",
            command=lambda: self._assign_individual_training(selected_player)
        )
        
        context_menu.add_command(
            label="📈 View Development History",
            command=lambda: self._view_development_history(selected_player)
        )
        
        context_menu.add_separator()
        
        context_menu.add_command(
            label="💼 Contract Details",
            command=lambda: self._view_contract_details(selected_player)
        )
        
        # Show menu
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _view_player_profile(self, player):
        """Open player profile window"""
        try:
            from ui_components import PlayerProfileWindow
            PlayerProfileWindow(self.parent, player)
        except ImportError:
            messagebox.showinfo("Player Profile", 
                              f"Viewing profile for {player.full_name}\n\n"
                              f"Position: {player.primary_position.value}\n"
                              f"Age: {player.age}\n"
                              f"Overall: {player.overall_rating()}")
    
    def _scout_player(self, player):
        """Scout player functionality"""
        messagebox.showinfo("Scouting Report", 
                          f"Scouting {player.full_name}...\n\n"
                          f"Position: {player.primary_position.value}\n"
                          f"Age: {player.age}\n"
                          f"Current Rating: {player.overall_rating()}\n"
                          f"Potential: {getattr(player, 'potential', 'Unknown')}\n\n"
                          f"Scout's Assessment: This player shows good development potential "
                          f"for their age group and position.")
    
    def _add_to_shortlist(self, player):
        """Add player to shortlist"""
        result = messagebox.askyesno("Add to Shortlist", 
                                   f"Add {player.full_name} to your shortlist?\n\n"
                                   f"This will help you track their progress and "
                                   f"receive notifications about their development.")
        if result:
            messagebox.showinfo("Added to Shortlist", 
                              f"{player.full_name} has been added to your shortlist.")
    
    def _compare_players(self, player):
        """Compare players functionality"""
        # Create a simple comparison window
        compare_window = tk.Toplevel(self)
        compare_window.title(f"Compare Players - {player.full_name}")
        compare_window.geometry("600x400")
        compare_window.configure(bg=self.parent.BG_COLOR)
        
        # Header
        header_label = ttk.Label(compare_window, 
                               text=f"Player Comparison - {player.full_name}",
                               style='DarkTitle.TLabel')
        header_label.pack(pady=20)
        
        # Instructions
        instructions = ttk.Label(compare_window,
                               text="Select another player to compare attributes and potential",
                               style='Dark.TLabel')
        instructions.pack(pady=10)
        
        # Player selection
        compare_frame = ttk.Frame(compare_window, style='Dark.TFrame')
        compare_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(compare_frame, text="Compare with:", style='DarkBold.TLabel').pack(anchor='w')
        
        # Get all players for comparison
        all_players = []
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            all_players = (self.parent.user_team.roster + 
                          self.parent.user_team.ahl_roster + 
                          self.parent.user_team.prospects)
        
        compare_var = tk.StringVar(master=compare_window)
        compare_combo = ttk.Combobox(compare_frame, textvariable=compare_var, 
                                   values=[p.full_name for p in all_players if p != player],
                                   state='readonly', width=40)
        compare_combo.pack(anchor='w', pady=10, fill='x')
        
        def do_comparison():
            selected_name = compare_var.get()
            if selected_name:
                compare_player = next((p for p in all_players if p.full_name == selected_name), None)
                if compare_player:
                    self._show_comparison_results(player, compare_player, compare_window)
        
        compare_btn = ttk.Button(compare_frame, text="Compare Players", command=do_comparison)
        compare_btn.pack(pady=10)
    
    def _show_comparison_results(self, player1, player2, parent_window):
        """Show detailed player comparison"""
        # Clear parent window and show results
        for widget in parent_window.winfo_children():
            widget.destroy()
            
        parent_window.title(f"Comparison: {player1.full_name} vs {player2.full_name}")
        
        # Results frame
        results_frame = ttk.Frame(parent_window, style='Dark.TFrame')
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header
        header = ttk.Label(results_frame, 
                         text=f"{player1.full_name} vs {player2.full_name}",
                         style='DarkTitle.TLabel')
        header.pack(pady=(0, 20))
        
        # Comparison grid
        comparison_data = [
            ("Overall Rating", player1.overall_rating(), player2.overall_rating()),
            ("Age", player1.age, player2.age),
            ("Potential", getattr(player1, 'potential', 'N/A'), getattr(player2, 'potential', 'N/A')),
            ("Skating", getattr(player1, 'skating', 'N/A'), getattr(player2, 'skating', 'N/A')),
            ("Shooting", getattr(player1, 'shooting', 'N/A'), getattr(player2, 'shooting', 'N/A')),
            ("Passing", getattr(player1, 'passing', 'N/A'), getattr(player2, 'passing', 'N/A')),
        ]
        
        for stat, val1, val2 in comparison_data:
            row = ttk.Frame(results_frame, style='Dark.TFrame')
            row.pack(fill='x', pady=5)
            
            ttk.Label(row, text=stat, style='DarkBold.TLabel', width=15).pack(side='left')
            ttk.Label(row, text=str(val1), style='Dark.TLabel', width=10).pack(side='left', padx=20)
            ttk.Label(row, text="vs", style='Dark.TLabel', width=5).pack(side='left')
            ttk.Label(row, text=str(val2), style='Dark.TLabel', width=10).pack(side='left', padx=20)
            
            # Show advantage
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if val1 > val2:
                    advantage = ttk.Label(row, text="←", foreground=self.parent.ACCENT_COLOR)
                elif val2 > val1:
                    advantage = ttk.Label(row, text="→", foreground=self.parent.ACCENT_COLOR)
                else:
                    advantage = ttk.Label(row, text="=", style='Dark.TLabel')
                advantage.pack(side='left', padx=10)
    
    def _assign_individual_training(self, player):
        """Quick training assignment for individual player"""
        # Switch to Individual Development tab and pre-select this player
        self.notebook.select(1)  # Select Individual Development tab
        
        if hasattr(self, 'training_player_var'):
            # Find and select this player in the combo
            player_text = f"{player.full_name} ({player.primary_position.value}, {player.age})"
            self.training_player_var.set(player_text)
            self._on_training_player_select(None)
            
        messagebox.showinfo("Training Assignment", 
                          f"Switched to Individual Development tab.\n"
                          f"{player.full_name} is now selected for training assignment.")
    
    def _view_development_history(self, player):
        """View player development history"""
        history_window = tk.Toplevel(self)
        history_window.title(f"Development History - {player.full_name}")
        history_window.geometry("500x400")
        history_window.configure(bg=self.parent.BG_COLOR)
        
        # Header
        header = ttk.Label(history_window, 
                         text=f"Development History\n{player.full_name}",
                         style='DarkTitle.TLabel')
        header.pack(pady=20)
        
        # Development info
        info_frame = ttk.Frame(history_window, style='Dark.TFrame')
        info_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        current_stage = "Developing"  # This would come from development engine
        ttk.Label(info_frame, text=f"Current Development Stage: {current_stage}", 
                 style='DarkBold.TLabel').pack(anchor='w', pady=5)
        
        ttk.Label(info_frame, text="Recent Development Activities:", 
                 style='DarkBold.TLabel').pack(anchor='w', pady=(20, 5))
        
        # Mock history entries
        history_entries = [
            "• Completed skating drills training program",
            "• Overall rating increased from 72 to 74",
            "• Assigned to intensive conditioning program",
            "• Participated in team scrimmage",
            "• Development assessment: Above average progress"
        ]
        
        for entry in history_entries:
            ttk.Label(info_frame, text=entry, style='Dark.TLabel').pack(anchor='w', pady=2)
    
    def _view_contract_details(self, player):
        """View player contract details"""
        contract_window = tk.Toplevel(self)
        contract_window.title(f"Contract Details - {player.full_name}")
        contract_window.geometry("400x300")
        contract_window.configure(bg=self.parent.BG_COLOR)
        
        # Header
        header = ttk.Label(contract_window, 
                         text=f"Contract Information\n{player.full_name}",
                         style='DarkTitle.TLabel')
        header.pack(pady=20)
        
        # Contract info
        info_frame = ttk.Frame(contract_window, style='Dark.TFrame')
        info_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Get contract details (mock for now)
        if hasattr(player, 'contract') and player.contract:
            salary = f"${getattr(player.contract, 'salary', 750000):,}"
            years = getattr(player.contract, 'years', 1)
            contract_type = getattr(player.contract, 'contract_type', 'Standard')
        else:
            salary = "$750,000"
            years = 1
            contract_type = "Entry Level"
        
        contract_details = [
            ("Salary:", salary),
            ("Contract Length:", f"{years} year(s)"),
            ("Contract Type:", contract_type),
            ("Status:", "Active"),
        ]
        
        for label, value in contract_details:
            row = ttk.Frame(info_frame, style='Dark.TFrame')
            row.pack(fill='x', pady=5)
            
            ttk.Label(row, text=label, style='DarkBold.TLabel', width=15).pack(side='left')
            ttk.Label(row, text=value, style='Dark.TLabel').pack(side='left', padx=10)
    
    def _show_details_context_menu(self, event, player):
        """Show context menu for player in details panel"""
        context_menu = tk.Menu(self, tearoff=0)
        context_menu.configure(bg=self.parent.CONTENT_BG, 
                             fg=self.parent.TEXT_COLOR,
                             activebackground=self.parent.ACCENT_COLOR,
                             activeforeground='white',
                             font=('Segoe UI', 9))
        
        context_menu.add_command(
            label=f"👤 View Full Profile",
            command=lambda: self._view_player_profile(player)
        )
        
        context_menu.add_command(
            label="🎯 Quick Training Assignment", 
            command=lambda: self._assign_individual_training(player)
        )
        
        context_menu.add_command(
            label="📊 Compare with Another Player",
            command=lambda: self._compare_players(player)
        )
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()