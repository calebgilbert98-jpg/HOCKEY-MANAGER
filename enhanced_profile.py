"""
Enhanced player profile display for Hockey Manager.
Contains a redesigned, professional player profile window with detailed stats and visualization.
"""

import tkinter as tk
from tkinter import ttk
import random
from datetime import date

class EnhancedPlayerProfileWindow(tk.Toplevel):
    """
    An enhanced window to display detailed player information with modern UI design.
    Features multiple tabs for different aspects of player information, stat visualizations,
    and comparison tools.
    """
    def __init__(self, parent, player, is_scouted=False, report=None):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.is_scouted = is_scouted
        self.report = report
        
        self.title(f"Player Profile: {player.full_name}")
        self.geometry("1000x750")
        self.configure(background=parent.BG_COLOR)
        self.minsize(800, 600)

        # Create styles
        self.style = parent.style
        self._setup_local_styles()
        
        # Create and pack main container
        self.main_frame = ttk.Frame(self, style='Panel.TFrame', padding=10)
        self.main_frame.pack(fill='both', expand=True)
        
        # Build the interface
        self._create_header_section()
        self._create_main_content()
        
        # Add team logo to the silhouette if part of a team
        if hasattr(player, 'team_name') and player.team_name:
            self._add_team_badge()
            
    def _setup_local_styles(self):
        """Configure styles specific to the player profile window."""
        # Attribute rating styles
        self.style.configure('Elite.TLabel', background="#2E7D32", foreground='white', 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=3)
        self.style.configure('Good.TLabel', background="#388E3C", foreground='white', 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=3)
        self.style.configure('Average.TLabel', background="#FBC02D", foreground='black', 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=3)
        self.style.configure('Below.TLabel', background="#E64A19", foreground='white', 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=3)
        self.style.configure('Poor.TLabel', background="#D32F2F", foreground='white', 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=3)
        
        # Other styles
        self.style.configure('Stat.TLabel', foreground=self.parent.TEXT_COLOR, 
                           font=(self.parent.FONT_FAMILY, 9))
        self.style.configure('StatHeader.TLabel', foreground=self.parent.HEADER_COLOR, 
                           font=(self.parent.FONT_FAMILY, 9, 'bold'))
        self.style.configure('PlayerName.TLabel', foreground=self.parent.HEADER_COLOR, 
                           font=(self.parent.FONT_FAMILY, 18, 'bold'))
        self.style.configure('PlayerDetails.TLabel', foreground=self.parent.TEXT_COLOR, 
                           font=(self.parent.FONT_FAMILY, 11))
        self.style.configure('SectionHeader.TLabel', foreground=self.parent.HEADER_COLOR, 
                           font=(self.parent.FONT_FAMILY, 14, 'bold'))
        self.style.configure('Badge.TLabel', foreground='white', background=self.parent.ACCENT_COLOR, 
                           font=(self.parent.FONT_FAMILY, 10, 'bold'), padding=5)
        
        # Progress bar style for attribute visualization
        self.style.configure("Attribute.Horizontal.TProgressbar", 
                           background=self.parent.ACCENT_COLOR, 
                           troughcolor=self.parent.CONTENT_BG)
        
    def _get_attribute_style(self, value):
        """Returns a style name based on the attribute value."""
        if value >= 18:
            return "Elite.TLabel"
        elif value >= 15:
            return "Good.TLabel"
        elif value >= 10:
            return "Average.TLabel"
        elif value >= 7:
            return "Below.TLabel"
        else:
            return "Poor.TLabel"
            
    def _create_header_section(self):
        """Create the header section with player name, basic info, and overall rating."""
        header_frame = ttk.Frame(self.main_frame, style='Panel.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))
        
        # Player name and position with jersey number
        name_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        name_frame.pack(side='left', fill='y')
        
        jersey_label = ttk.Label(name_frame, text=f"#{self.player.jersey_number}", 
                               style='Badge.TLabel')
        jersey_label.pack(side='left', padx=(0, 10))
        
        player_name = ttk.Label(name_frame, 
                              text=f"{self.player.full_name}", 
                              style='PlayerName.TLabel')
        player_name.pack(side='left')
        
        position_text = self.player.primary_position.name.replace('_', ' ')
        position_label = ttk.Label(name_frame, 
                                 text=f" - {position_text}", 
                                 style='PlayerDetails.TLabel')
        position_label.pack(side='left')
        
        # Basic player info
        if hasattr(self.player, 'team_name') and self.player.team_name:
            team_label = ttk.Label(name_frame, 
                                 text=f" | {self.player.team_name}", 
                                 style='PlayerDetails.TLabel')
            team_label.pack(side='left')
        
        # Right side - overall rating badge
        rating_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        rating_frame.pack(side='right')
        
        overall = self.player.overall_rating()
        overall_label = ttk.Label(rating_frame, 
                                text=f"OVERALL\n{overall}", 
                                style=self._get_attribute_style(overall))
        overall_label.pack(side='right', padx=5)
        
        # Add potential if it exists
        if hasattr(self.player, 'potential_grade'):
            potential_label = ttk.Label(rating_frame, 
                                      text=f"POTENTIAL\n{self.player.potential_grade}", 
                                      style='Badge.TLabel')
            potential_label.pack(side='right', padx=5)
            
        # Show captaincy if applicable
        if hasattr(self.player, 'captaincy') and self.player.captaincy:
            captaincy_text = "CAPTAIN" if self.player.captaincy == 'C' else "ALTERNATE"
            captaincy_label = ttk.Label(rating_frame, 
                                      text=captaincy_text, 
                                      style='Badge.TLabel')
            captaincy_label.pack(side='right', padx=5)
            
    def _create_main_content(self):
        """Create the tabbed interface for player information."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Create the tabs
        overview_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        attributes_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        stats_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        contract_tab = ttk.Frame(self.notebook, style='Panel.TFrame')
        
        # Add tabs to notebook
        self.notebook.add(overview_tab, text="Overview")
        self.notebook.add(attributes_tab, text="Attributes")
        self.notebook.add(stats_tab, text="Statistics")
        self.notebook.add(contract_tab, text="Contract")
        
        # Build tab content
        self._build_overview_tab(overview_tab)
        self._build_attributes_tab(attributes_tab)
        self._build_stats_tab(stats_tab)
        self._build_contract_tab(contract_tab)
    
    def _build_overview_tab(self, tab_frame):
        """Build the overview tab with player bio, key stats, and summary."""
        # Create columns for layout
        columns_frame = ttk.Frame(tab_frame, style='Panel.TFrame')
        columns_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left column - Player silhouette and bio
        left_col = ttk.Frame(columns_frame, style='Panel.TFrame')
        left_col.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Player silhouette/image placeholder
        silhouette_frame = ttk.LabelFrame(left_col, text="Player", style='Panel.TLabelframe')
        silhouette_frame.pack(fill='x', expand=False, pady=5)
        
        canvas_height = 220
        silhouette_canvas = tk.Canvas(silhouette_frame, width=180, height=canvas_height, 
                                    bg=self.parent.CONTENT_BG, highlightthickness=0)
        silhouette_canvas.pack(pady=10)
        
        # Draw player silhouette
        if self.player.primary_position.name == "G":
            # Goalie silhouette
            silhouette_canvas.create_rectangle(60, 30, 120, 70, fill="#555555", outline="")  # Helmet
            silhouette_canvas.create_rectangle(50, 70, 130, 140, fill="#666666", outline="")  # Body
            silhouette_canvas.create_rectangle(30, 100, 50, 140, fill="#666666", outline="")  # Left arm
            silhouette_canvas.create_rectangle(130, 100, 150, 140, fill="#666666", outline="")  # Right arm
            silhouette_canvas.create_rectangle(50, 140, 70, 200, fill="#777777", outline="")  # Left leg
            silhouette_canvas.create_rectangle(110, 140, 130, 200, fill="#777777", outline="")  # Right leg
            silhouette_canvas.create_rectangle(40, 70, 140, 90, fill="#555555", outline="")  # Chest protector
        else:
            # Skater silhouette
            silhouette_canvas.create_oval(70, 20, 110, 60, fill="#555555", outline="")  # Head
            silhouette_canvas.create_rectangle(60, 60, 120, 130, fill="#666666", outline="")  # Body
            silhouette_canvas.create_line(40, 90, 60, 80, fill="#777777", width=5)  # Left arm
            silhouette_canvas.create_line(140, 90, 120, 80, fill="#777777", width=5)  # Right arm
            silhouette_canvas.create_line(70, 130, 60, 190, fill="#777777", width=5)  # Left leg
            silhouette_canvas.create_line(110, 130, 120, 190, fill="#777777", width=5)  # Right leg
            
        # Store canvas for later team badge addition
        self.silhouette_canvas = silhouette_canvas
        
        # Player bio information
        bio_frame = ttk.LabelFrame(left_col, text="Player Information", style='Panel.TLabelframe')
        bio_frame.pack(fill='x', expand=False, pady=5)
        
        # Create two columns for bio info
        bio_columns = ttk.Frame(bio_frame, style='Panel.TFrame')
        bio_columns.pack(fill='x', padx=10, pady=10)
        bio_columns.columnconfigure(0, weight=1)
        bio_columns.columnconfigure(1, weight=1)
        
        # Bio info
        bio_data = [
            ("Age:", f"{self.player.age} years"),
            ("Born:", self._get_random_birthplace()),
            ("Height:", f"{self._get_random_height()}"),
            ("Weight:", f"{self._get_random_weight()} lbs"),
            ("Position:", self.player.primary_position.name.replace('_', ' ')),
            ("Shoots:", "Left" if random.random() < 0.7 else "Right"),
            ("Experience:", f"{max(0, self.player.age - 18)} years"),
            ("Draft:", f"Round {random.randint(1, 7)}, {2020 - (self.player.age - 18)}")
        ]
        
        for i, (label, value) in enumerate(bio_data):
            row = i // 2
            col = i % 2
            ttk.Label(bio_columns, text=label, style='StatHeader.TLabel').grid(
                row=row, column=col*2, sticky='w', padx=5, pady=3)
            ttk.Label(bio_columns, text=value, style='Stat.TLabel').grid(
                row=row, column=col*2+1, sticky='w', padx=5, pady=3)
                
        # Key strengths
        strengths_frame = ttk.LabelFrame(left_col, text="Key Strengths", style='Panel.TLabelframe')
        strengths_frame.pack(fill='both', expand=True, pady=5)
        
        strengths = self._identify_player_strengths()
        for strength in strengths[:5]:  # Show top 5 strengths
            strength_label = ttk.Label(strengths_frame, 
                                     text=f"• {strength[0]}: {strength[1]}", 
                                     style='Stat.TLabel')
            strength_label.pack(anchor='w', padx=10, pady=2)
        
        # Right column - Summary, season stats, comparison
        right_col = ttk.Frame(columns_frame, style='Panel.TFrame')
        right_col.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Player summary/scouting report
        summary_frame = ttk.LabelFrame(right_col, text="Player Summary", style='Panel.TLabelframe')
        summary_frame.pack(fill='x', expand=False, pady=5)
        
        summary_text = self._generate_player_summary()
        summary = tk.Text(summary_frame, wrap='word', height=6, 
                         bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                         font=(self.parent.FONT_FAMILY, 10))
        summary.pack(fill='both', expand=True, padx=10, pady=10)
        summary.insert('1.0', summary_text)
        summary.config(state='disabled')
        
        # Current season stats
        season_frame = ttk.LabelFrame(right_col, text="Current Season Stats", style='Panel.TLabelframe')
        season_frame.pack(fill='x', expand=False, pady=5)
        
        # Stats columns
        stats_grid = ttk.Frame(season_frame, style='Panel.TFrame')
        stats_grid.pack(fill='x', padx=10, pady=10)
        
        # Different stats based on position
        if self.player.primary_position.name == "G":
            # Goalie stats
            goalie_stats = [
                ("Games", random.randint(20, 60)),
                ("Wins", random.randint(10, 40)),
                ("GAA", round(random.uniform(1.8, 3.5), 2)),
                ("SV%", round(random.uniform(0.89, 0.93), 3)),
                ("SO", random.randint(0, 8))
            ]
            
            for i, (stat, value) in enumerate(goalie_stats):
                ttk.Label(stats_grid, text=stat, style='StatHeader.TLabel').grid(
                    row=0, column=i, padx=10, pady=5)
                ttk.Label(stats_grid, text=str(value), style='Stat.TLabel').grid(
                    row=1, column=i, padx=10, pady=5)
        else:
            # Skater stats
            skater_stats = [
                ("GP", random.randint(40, 82)),
                ("G", self.player.stats.goals),
                ("A", self.player.stats.assists),
                ("P", self.player.stats.points),
                ("PIM", self.player.stats.penalties_in_minutes),
                ("+/-", random.randint(-20, 20))
            ]
            
            for i, (stat, value) in enumerate(skater_stats):
                ttk.Label(stats_grid, text=stat, style='StatHeader.TLabel').grid(
                    row=0, column=i, padx=10, pady=5)
                ttk.Label(stats_grid, text=str(value), style='Stat.TLabel').grid(
                    row=1, column=i, padx=10, pady=5)
        
        # Attribute radar chart (simplified with key attributes)
        attributes_frame = ttk.LabelFrame(right_col, text="Key Attributes", style='Panel.TLabelframe')
        attributes_frame.pack(fill='both', expand=True, pady=5)
        
        # Key attributes progress bars
        key_attrs = self._get_key_attributes()
        for i, (attr_name, attr_value) in enumerate(key_attrs):
            attr_frame = ttk.Frame(attributes_frame, style='Panel.TFrame')
            attr_frame.pack(fill='x', padx=10, pady=3)
            
            # Label
            ttk.Label(attr_frame, text=attr_name, style='Stat.TLabel', width=15).pack(side='left')
            
            # Progress bar
            progress = ttk.Progressbar(attr_frame, style="Attribute.Horizontal.TProgressbar", 
                                     length=200, maximum=20, value=attr_value)
            progress.pack(side='left', padx=5)
            
            # Value with color coding
            ttk.Label(attr_frame, text=str(attr_value), 
                    style=self._get_attribute_style(attr_value)).pack(side='left')
        
        # Contract overview
        contract_frame = ttk.LabelFrame(right_col, text="Contract Status", style='Panel.TLabelframe')
        contract_frame.pack(fill='x', expand=False, pady=5)
        
        contract_info = ttk.Frame(contract_frame, style='Panel.TFrame')
        contract_info.pack(fill='x', padx=10, pady=10)
        
        contract_details = [
            ("Current Salary:", f"${self.player.contract.salary:,}"),
            ("Years Remaining:", self.player.contract.years_remaining),
            ("Clauses:", "No-Trade" if hasattr(self.player.contract, 'no_trade_clause') and 
                       self.player.contract.no_trade_clause else "None")
        ]
        
        for i, (label, value) in enumerate(contract_details):
            ttk.Label(contract_info, text=label, style='StatHeader.TLabel').grid(
                row=i, column=0, sticky='w', padx=5, pady=3)
            ttk.Label(contract_info, text=str(value), style='Stat.TLabel').grid(
                row=i, column=1, sticky='w', padx=5, pady=3)
    
    def _build_attributes_tab(self, tab_frame):
        """Build the detailed attributes tab with all player attributes."""
        # Create scrollable canvas for attributes
        canvas = tk.Canvas(tab_frame, bg=self.parent.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create category frames
        categories = self._get_attribute_categories()
        
        # Create 3-column layout
        main_grid = ttk.Frame(scrollable_frame, style='Panel.TFrame')
        main_grid.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Organize attributes by category with 3 columns
        col = 0
        row = 0
        max_attrs_per_col = len(sum(categories.values(), [])) // 3 + 1
        attrs_in_col = 0
        
        for category, attributes in categories.items():
            # Check if we need to move to next column
            if attrs_in_col + len(attributes) > max_attrs_per_col and col < 2:
                col += 1
                row = 0
                attrs_in_col = 0
            
            # Create category header
            category_frame = ttk.LabelFrame(main_grid, text=category, style='Panel.TLabelframe')
            category_frame.grid(row=row, column=col, sticky='ew', padx=5, pady=5)
            row += 1
            attrs_in_col += len(attributes) + 1  # +1 for the header
            
            # Add attributes to category
            for i, (attr_name, attr_value) in enumerate(attributes):
                attr_frame = ttk.Frame(category_frame, style='Panel.TFrame')
                attr_frame.pack(fill='x', padx=5, pady=2)
                
                # Name and value
                ttk.Label(attr_frame, text=attr_name, style='Stat.TLabel', width=15).pack(side='left')
                ttk.Label(attr_frame, text=str(attr_value), 
                        style=self._get_attribute_style(attr_value), width=3).pack(side='right')
                
                # Progress bar
                progress = ttk.Progressbar(attr_frame, style="Attribute.Horizontal.TProgressbar", 
                                         length=120, maximum=20, value=attr_value)
                progress.pack(side='right', padx=5)
    
    def _build_stats_tab(self, tab_frame):
        """Build the statistics tab with detailed stats history."""
        # Career stats section
        stats_frame = ttk.Frame(tab_frame, style='Panel.TFrame', padding=10)
        stats_frame.pack(fill='both', expand=True)
        
        # Regular season stats
        regular_label = ttk.Label(stats_frame, text="Regular Season Statistics", 
                                style='SectionHeader.TLabel')
        regular_label.pack(anchor='w', pady=(0, 10))
        
        # Stats table - columns depend on position
        if self.player.primary_position.name == "G":
            # Goalie stats columns
            columns = {
                'season': ('Season', 100), 
                'team': ('Team', 120), 
                'gp': ('GP', 50), 
                'w': ('W', 50), 
                'l': ('L', 50), 
                'otl': ('OTL', 50), 
                'gaa': ('GAA', 60), 
                'sv_pct': ('SV%', 60), 
                'so': ('SO', 50)
            }
        else:
            # Skater stats columns
            columns = {
                'season': ('Season', 100), 
                'team': ('Team', 120), 
                'gp': ('GP', 50), 
                'g': ('G', 50), 
                'a': ('A', 50), 
                'p': ('P', 50), 
                'pm': ('+/-', 50), 
                'pim': ('PIM', 50), 
                'toi': ('TOI', 60)
            }
            
        # Create stats treeview
        stats_tree = ttk.Treeview(stats_frame, columns=list(columns.keys()), 
                                show='headings', height=10)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            stats_tree.heading(col_id, text=header)
            stats_tree.column(col_id, width=width, anchor='center')
        
        stats_tree.pack(fill='x', pady=5)
        
        # Generate some random stats history
        current_year = date.today().year
        team_name = getattr(self.player, 'team_name', "Free Agent")
        
        for i in range(min(5, max(1, self.player.age - 18))):
            season_year = current_year - i
            season = f"{season_year-1}-{str(season_year)[2:]}"
            
            if self.player.primary_position.name == "G":
                # Goalie stats
                games = random.randint(20, 60)
                wins = random.randint(5, games-10)
                losses = random.randint(5, games-wins-5)
                otl = games - wins - losses
                gaa = round(random.uniform(1.8, 3.5), 2)
                sv_pct = round(random.uniform(0.89, 0.93), 3)
                shutouts = random.randint(0, 8)
                
                values = (season, team_name, games, wins, losses, otl, gaa, sv_pct, shutouts)
            else:
                # Skater stats
                games = random.randint(40, 82)
                goals = random.randint(5, 30) if i == 0 else self.player.stats.goals
                assists = random.randint(10, 50) if i == 0 else self.player.stats.assists
                points = goals + assists
                plus_minus = random.randint(-20, 20)
                pim = random.randint(10, 80) if i == 0 else self.player.stats.penalties_in_minutes
                toi = f"{random.randint(12, 22)}:{random.randint(0, 59):02d}"
                
                values = (season, team_name, games, goals, assists, points, plus_minus, pim, toi)
                
            stats_tree.insert('', 'end', values=values)
            
        # Playoff stats
        playoff_label = ttk.Label(stats_frame, text="Playoff Statistics", 
                                style='SectionHeader.TLabel')
        playoff_label.pack(anchor='w', pady=(20, 10))
        
        # Create playoff stats treeview
        playoff_tree = ttk.Treeview(stats_frame, columns=list(columns.keys()), 
                                  show='headings', height=5)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            playoff_tree.heading(col_id, text=header)
            playoff_tree.column(col_id, width=width, anchor='center')
        
        playoff_tree.pack(fill='x', pady=5)
        
        # Generate some playoff stats (fewer entries)
        for i in range(min(3, max(0, self.player.age - 20))):
            season_year = current_year - i - random.randint(0, 2)
            season = f"{season_year-1}-{str(season_year)[2:]}"
            
            if self.player.primary_position.name == "G":
                # Goalie playoff stats (usually fewer games)
                games = random.randint(4, 25)
                wins = random.randint(4, min(16, games))  # Max 16 wins in playoffs
                losses = games - wins
                otl = 0  # No OTL in playoffs
                gaa = round(random.uniform(1.7, 3.2), 2)  # Slightly better in playoffs
                sv_pct = round(random.uniform(0.90, 0.94), 3)
                shutouts = random.randint(0, 4)
                
                values = (season, team_name, games, wins, losses, otl, gaa, sv_pct, shutouts)
            else:
                # Skater playoff stats
                games = random.randint(4, 28)
                goals = random.randint(1, 10)
                assists = random.randint(2, 15)
                points = goals + assists
                plus_minus = random.randint(-10, 15)
                pim = random.randint(2, 40)
                toi = f"{random.randint(14, 24)}:{random.randint(0, 59):02d}"  # Usually more TOI in playoffs
                
                values = (season, team_name, games, goals, assists, points, plus_minus, pim, toi)
                
            playoff_tree.insert('', 'end', values=values)
            
        # Add career highs section
        highs_label = ttk.Label(stats_frame, text="Career Highlights", 
                              style='SectionHeader.TLabel')
        highs_label.pack(anchor='w', pady=(20, 10))
        
        # Career highs frame
        highs_frame = ttk.Frame(stats_frame, style='Panel.TFrame')
        highs_frame.pack(fill='x', pady=5)
        
        # Generate career highs
        if self.player.primary_position.name == "G":
            # Goalie career highs
            career_highs = [
                ("Most Wins in a Season:", f"{random.randint(20, 45)} ({current_year-random.randint(0, 5)})"),
                ("Best Save Percentage:", f".{random.randint(915, 935)} ({current_year-random.randint(0, 5)})"),
                ("Most Shutouts:", f"{random.randint(3, 10)} ({current_year-random.randint(0, 5)})"),
                ("Lowest GAA:", f"{round(random.uniform(1.5, 2.5), 2)} ({current_year-random.randint(0, 5)})")
            ]
        else:
            # Skater career highs
            career_highs = [
                ("Most Goals in a Season:", f"{random.randint(15, 50)} ({current_year-random.randint(0, 5)})"),
                ("Most Assists in a Season:", f"{random.randint(20, 60)} ({current_year-random.randint(0, 5)})"),
                ("Most Points in a Season:", f"{random.randint(40, 100)} ({current_year-random.randint(0, 5)})"),
                ("Best Plus/Minus:", f"+{random.randint(10, 40)} ({current_year-random.randint(0, 5)})")
            ]
            
        # Two columns for career highs
        highs_cols = ttk.Frame(highs_frame, style='Panel.TFrame')
        highs_cols.pack(fill='x')
        
        for i, (stat, value) in enumerate(career_highs):
            col = i % 2
            row = i // 2
            
            stat_frame = ttk.Frame(highs_cols, style='Panel.TFrame')
            stat_frame.grid(row=row, column=col, sticky='w', padx=10, pady=5)
            
            ttk.Label(stat_frame, text=stat, style='StatHeader.TLabel').pack(side='left')
            ttk.Label(stat_frame, text=value, style='Stat.TLabel').pack(side='left', padx=5)
    
    def _build_contract_tab(self, tab_frame):
        """Build the contract tab with salary details and negotiation history."""
        contract_frame = ttk.Frame(tab_frame, style='Panel.TFrame', padding=10)
        contract_frame.pack(fill='both', expand=True)
        
        # Current contract details
        current_label = ttk.Label(contract_frame, text="Current Contract", 
                                style='SectionHeader.TLabel')
        current_label.pack(anchor='w', pady=(0, 10))
        
        # Contract details frame
        details_frame = ttk.Frame(contract_frame, style='Panel.TFrame', padding=10)
        details_frame.pack(fill='x', pady=5)
        
        # Two columns layout
        details_cols = ttk.Frame(details_frame, style='Panel.TFrame')
        details_cols.pack(fill='x')
        details_cols.columnconfigure(0, weight=1)
        details_cols.columnconfigure(1, weight=1)
        
        # Contract details
        contract_details = [
            ("Annual Salary:", f"${self.player.contract.salary:,}"),
            ("Contract Length:", f"{self.player.contract.years_remaining} years remaining"),
            ("Signing Bonus:", f"${getattr(self.player.contract, 'signing_bonus', 0):,}"),
            ("No-Trade Clause:", "Yes" if getattr(self.player.contract, 'no_trade_clause', False) else "No"),
            ("Performance Bonuses:", f"${getattr(self.player.contract, 'performance_bonus', 0):,}"),
            ("Contract Type:", "Standard Player Contract"),
            ("Expiry Status:", "UFA" if self.player.age >= 27 else "RFA"),
            ("Cap Hit:", f"${self.player.contract.salary:,}")
        ]
        
        for i, (label, value) in enumerate(contract_details):
            row = i % 4
            col = i // 4
            
            ttk.Label(details_cols, text=label, style='StatHeader.TLabel').grid(
                row=row, column=col*2, sticky='w', padx=5, pady=5)
            ttk.Label(details_cols, text=value, style='Stat.TLabel').grid(
                row=row, column=col*2+1, sticky='w', padx=5, pady=5)
        
        # Visual salary breakdown
        breakdown_label = ttk.Label(contract_frame, text="Salary Breakdown", 
                                  style='SectionHeader.TLabel')
        breakdown_label.pack(anchor='w', pady=(20, 10))
        
        # Breakdown chart
        breakdown_frame = ttk.Frame(contract_frame, style='Panel.TFrame')
        breakdown_frame.pack(fill='x', pady=5)
        
        # Create breakdown visualization
        canvas = tk.Canvas(breakdown_frame, height=150, bg=self.parent.CONTENT_BG, highlightthickness=0)
        canvas.pack(fill='x', padx=10, pady=10)
        
        # Determine how many years to show
        years_to_show = max(1, self.player.contract.years_remaining)
        current_year = date.today().year
        
        # Draw salary bars
        bar_width = min(80, (canvas.winfo_reqwidth() - 100) / years_to_show)
        max_height = 100
        
        # Calculate max salary for scaling
        base_salary = self.player.contract.salary
        signing_bonus = getattr(self.player.contract, 'signing_bonus', 0)
        performance_bonus = getattr(self.player.contract, 'performance_bonus', 0)
        max_salary_amount = max(base_salary + signing_bonus, base_salary + performance_bonus)
        
        # Ensure we have at least 1M headroom
        max_salary_amount = max(max_salary_amount + 1000000, max_salary_amount * 1.2)
        
        # Draw salary bars for each year of contract
        for i in range(years_to_show):
            x_pos = 50 + i * (bar_width + 20)
            year_label = f"{current_year + i}"
            
            # Base salary
            base_height = (base_salary / max_salary_amount) * max_height
            canvas.create_rectangle(x_pos, 130 - base_height, x_pos + bar_width, 130, 
                                  fill=self.parent.ACCENT_COLOR, outline="")
            
            # Signing bonus (first year only)
            if i == 0 and signing_bonus > 0:
                bonus_height = (signing_bonus / max_salary_amount) * max_height
                canvas.create_rectangle(x_pos, 130 - base_height - bonus_height, 
                                      x_pos + bar_width, 130 - base_height, 
                                      fill="#FBC02D", outline="")
            
            # Performance bonus (potential)
            if performance_bonus > 0:
                perf_height = (performance_bonus / max_salary_amount) * max_height
                canvas.create_rectangle(x_pos + bar_width/2, 130 - base_height - perf_height, 
                                      x_pos + bar_width, 130 - base_height, 
                                      fill="#81C784", outline="")
            
            # Add year label
            canvas.create_text(x_pos + bar_width/2, 140, text=year_label, fill=self.parent.TEXT_COLOR)
            
            # Add salary amount
            canvas.create_text(x_pos + bar_width/2, 120 - base_height - 10, 
                             text=f"${base_salary/1000000:.1f}M", 
                             fill=self.parent.TEXT_COLOR, anchor='s')
        
        # Add legend
        legend_frame = ttk.Frame(breakdown_frame, style='Panel.TFrame')
        legend_frame.pack(fill='x', padx=10, pady=5)
        
        # Base salary
        base_frame = ttk.Frame(legend_frame, style='Panel.TFrame')
        base_frame.pack(side='left', padx=10)
        base_color = tk.Canvas(base_frame, width=15, height=15, bg=self.parent.ACCENT_COLOR, highlightthickness=0)
        base_color.pack(side='left')
        ttk.Label(base_frame, text="Base Salary", style='Stat.TLabel').pack(side='left', padx=5)
        
        # Signing bonus
        if signing_bonus > 0:
            signing_frame = ttk.Frame(legend_frame, style='Panel.TFrame')
            signing_frame.pack(side='left', padx=10)
            signing_color = tk.Canvas(signing_frame, width=15, height=15, bg="#FBC02D", highlightthickness=0)
            signing_color.pack(side='left')
            ttk.Label(signing_frame, text="Signing Bonus", style='Stat.TLabel').pack(side='left', padx=5)
        
        # Performance bonus
        if performance_bonus > 0:
            perf_frame = ttk.Frame(legend_frame, style='Panel.TFrame')
            perf_frame.pack(side='left', padx=10)
            perf_color = tk.Canvas(perf_frame, width=15, height=15, bg="#81C784", highlightthickness=0)
            perf_color.pack(side='left')
            ttk.Label(perf_frame, text="Performance Bonus (Potential)", style='Stat.TLabel').pack(side='left', padx=5)
        
        # Contract history
        history_label = ttk.Label(contract_frame, text="Contract History", 
                                style='SectionHeader.TLabel')
        history_label.pack(anchor='w', pady=(20, 10))
        
        # Contract history table
        columns = {
            'date': ('Date', 100), 
            'team': ('Team', 150), 
            'type': ('Type', 120), 
            'years': ('Years', 60), 
            'amount': ('Amount', 120),
            'aav': ('AAV', 100)
        }
        
        history_tree = ttk.Treeview(contract_frame, columns=list(columns.keys()), 
                                  show='headings', height=5)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            history_tree.heading(col_id, text=header)
            history_tree.column(col_id, width=width, anchor='center')
        
        history_tree.pack(fill='x', pady=5)
        
        # Generate random contract history
        current_year = date.today().year
        team_name = getattr(self.player, 'team_name', "Free Agent")
        
        # Initial entry-level contract
        draft_year = current_year - (self.player.age - 18)
        history_tree.insert('', 'end', values=(
            f"Jul 1, {draft_year}",
            team_name,
            "Entry-Level Contract",
            "3",
            f"${925000*3:,}",
            f"${925000:,}"
        ))
        
        # Add contract extensions or free agency signings if player is older
        if self.player.age >= 22:
            history_tree.insert('', 'end', values=(
                f"Jul 1, {draft_year+3}",
                team_name,
                "Contract Extension",
                "2",
                f"${2000000*2:,}",
                f"${2000000:,}"
            ))
            
        if self.player.age >= 25:
            new_team = "Toronto Maple Leafs" if team_name != "Toronto Maple Leafs" else "Edmonton Oilers"
            history_tree.insert('', 'end', values=(
                f"Jul 1, {draft_year+5}",
                new_team,
                "Free Agent Signing",
                "4",
                f"${5500000*4:,}",
                f"${5500000:,}"
            ))
            
        if self.player.age >= 30:
            history_tree.insert('', 'end', values=(
                f"Jul 1, {current_year-1}",
                team_name,
                "Free Agent Signing",
                f"{self.player.contract.years_remaining + 1}",
                f"${self.player.contract.salary * (self.player.contract.years_remaining + 1):,}",
                f"${self.player.contract.salary:,}"
            ))
            
    def _add_team_badge(self):
        """Add team badge to player silhouette."""
        if not hasattr(self, 'silhouette_canvas'):
            return
            
        # Create a simple team badge (would use team logo in a real implementation)
        badge_size = 40
        team_colors = {
            "Toronto Maple Leafs": "#00205B",
            "Montreal Canadiens": "#AF1E2D",
            "Boston Bruins": "#FFB81C",
            "New York Rangers": "#0038A8",
            "Chicago Blackhawks": "#CF0A2C",
            "Detroit Red Wings": "#CE1126",
            "Edmonton Oilers": "#FF4C00",
            "Vancouver Canucks": "#00843D",
            "Pittsburgh Penguins": "#FCB514",
            "Tampa Bay Lightning": "#002868"
        }
        
        team_name = self.player.team_name
        team_color = team_colors.get(team_name, "#777777")
        
        # Draw badge in bottom corner
        self.silhouette_canvas.create_oval(
            10, 
            self.silhouette_canvas.winfo_height() - 10 - badge_size,
            10 + badge_size,
            self.silhouette_canvas.winfo_height() - 10,
            fill=team_color, outline=""
        )
        
        # Add team initials
        initials = ''.join(word[0] for word in team_name.split()[:2])
        self.silhouette_canvas.create_text(
            10 + badge_size/2,
            self.silhouette_canvas.winfo_height() - 10 - badge_size/2,
            text=initials,
            fill="white",
            font=(self.parent.FONT_FAMILY, 12, 'bold')
        )
    
    # Helper methods for generating player data
    def _get_random_height(self):
        """Generate a random player height."""
        feet = random.randint(5, 6)
        inches = random.randint(7, 11) if feet == 5 else random.randint(0, 5)
        return f"{feet}' {inches}\""
    
    def _get_random_weight(self):
        """Generate a random player weight."""
        return random.randint(175, 235)
    
    def _get_random_birthplace(self):
        """Generate a random birthplace."""
        countries = {
            "Canada": 0.45,
            "USA": 0.25,
            "Sweden": 0.08,
            "Russia": 0.07,
            "Finland": 0.05,
            "Czech Republic": 0.04,
            "Switzerland": 0.02,
            "Germany": 0.02,
            "Slovakia": 0.01,
            "Other": 0.01
        }
        
        rand = random.random()
        cumulative = 0
        for country, prob in countries.items():
            cumulative += prob
            if rand <= cumulative:
                return country
        return "Canada"
    
    def _identify_player_strengths(self):
        """Identify the player's top strengths based on attributes."""
        attributes = []
        
        # Get all numeric attributes
        for attr_name in dir(self.player):
            if attr_name.startswith('_'):
                continue
                
            attr_value = getattr(self.player, attr_name)
            if isinstance(attr_value, int) and 1 <= attr_value <= 20:
                # Convert snake_case to Title Case
                display_name = ' '.join(word.capitalize() for word in attr_name.split('_'))
                attributes.append((display_name, attr_value))
        
        # Sort by value in descending order
        return sorted(attributes, key=lambda x: x[1], reverse=True)
    
    def _generate_player_summary(self):
        """Generate a descriptive player summary based on attributes."""
        # Get age category
        if self.player.age < 22:
            age_desc = "young"
        elif self.player.age < 28:
            age_desc = "prime-aged"
        elif self.player.age < 33:
            age_desc = "experienced"
        else:
            age_desc = "veteran"
            
        # Get overall category
        overall = self.player.overall_rating()
        if overall >= 88:
            skill_desc = "elite"
        elif overall >= 83:
            skill_desc = "star"
        elif overall >= 78:
            skill_desc = "top-tier"
        elif overall >= 73:
            skill_desc = "solid"
        else:
            skill_desc = "depth"
            
        # Get position
        pos = self.player.primary_position.name
        if pos == "G":
            pos_desc = "goaltender"
        elif pos in ["LD", "RD", "D"]:
            pos_desc = "defenseman"
        elif pos == "C":
            pos_desc = "center"
        else:
            pos_desc = "winger"
            
        # Get top 3 strengths
        strengths = self._identify_player_strengths()
        top_strengths = [s[0] for s in strengths[:3]]
        
        # Base summary
        summary = f"{self.player.full_name} is a {age_desc} {skill_desc} {pos_desc}. "
        
        # Add strengths
        if len(top_strengths) >= 3:
            summary += f"His greatest strengths are his {top_strengths[0]}, {top_strengths[1]}, and {top_strengths[2]}. "
        
        # Add specific trait based on position
        if pos == "G":
            if hasattr(self.player, 'reflexes') and self.player.reflexes >= 15:
                summary += "He has exceptional reflexes and is known for making spectacular saves. "
            elif hasattr(self.player, 'positioning') and self.player.positioning >= 15:
                summary += "He relies on excellent positioning rather than flashy saves. "
        elif pos in ["LD", "RD", "D"]:
            if hasattr(self.player, 'defensive_awareness') and self.player.defensive_awareness >= 15:
                summary += "He's a shutdown defender who excels in his own zone. "
            elif hasattr(self.player, 'offensive_awareness') and self.player.offensive_awareness >= 15:
                summary += "He's an offensive defenseman who contributes significantly to the attack. "
        elif pos == "C":
            if hasattr(self.player, 'faceoffs') and self.player.faceoffs >= 15:
                summary += "He's excellent in the faceoff circle, giving his team possession advantage. "
            elif hasattr(self.player, 'playmaking') and self.player.playmaking >= 15:
                summary += "He's a playmaker who creates scoring opportunities for his linemates. "
        else:  # Wingers
            if hasattr(self.player, 'shooting') and self.player.shooting >= 15:
                summary += "He's a sniper with a lethal shot who can finish plays. "
            elif hasattr(self.player, 'speed') and self.player.speed >= 15:
                summary += "His speed makes him dangerous on the rush and forecheck. "
        
        # Add potential note for young players
        if self.player.age < 25 and hasattr(self.player, 'potential_grade'):
            if self.player.potential_grade in ['A', 'B']:
                summary += "Scouts believe he has significant untapped potential and could develop into an elite player. "
            elif self.player.potential_grade in ['C', 'D']:
                summary += "He still has room to develop and improve his game. "
        
        # Add career note for veterans
        if self.player.age >= 33:
            summary += "Despite his age, he still brings valuable leadership and experience to the team. "
        
        return summary
    
    def _get_key_attributes(self):
        """Get key attributes based on player position."""
        # Common attributes
        attributes = [
            ("Skating", self.player.skating),
            ("Strength", self.player.strength)
        ]
        
        # Position-specific attributes
        pos = self.player.primary_position.name
        if pos == "G":
            # Goalie attributes
            goalie_attrs = [
                ("Reflexes", getattr(self.player, 'reflexes', 10)),
                ("Positioning", getattr(self.player, 'positioning', 10)),
                ("Rebound Control", getattr(self.player, 'rebound_control', 10)),
                ("Puck Handling", getattr(self.player, 'puck_handling', 10))
            ]
            attributes.extend(goalie_attrs)
        elif pos in ["LD", "RD", "D"]:
            # Defense attributes
            defense_attrs = [
                ("Checking", getattr(self.player, 'checking', 10)),
                ("Defensive Awareness", getattr(self.player, 'defensive_awareness', 10)),
                ("Shot Blocking", getattr(self.player, 'shot_blocking', 10)),
                ("Stick Checking", getattr(self.player, 'stick_checking', 10))
            ]
            attributes.extend(defense_attrs)
        elif pos == "C":
            # Center attributes
            center_attrs = [
                ("Faceoffs", getattr(self.player, 'faceoffs', 10)),
                ("Passing", getattr(self.player, 'passing', 10)),
                ("Offensive Awareness", getattr(self.player, 'offensive_awareness', 10)),
                ("Defensive Awareness", getattr(self.player, 'defensive_awareness', 10))
            ]
            attributes.extend(center_attrs)
        else:
            # Winger attributes
            winger_attrs = [
                ("Shooting", getattr(self.player, 'shooting', 10)),
                ("Offensive Awareness", getattr(self.player, 'offensive_awareness', 10)),
                ("Speed", getattr(self.player, 'speed', 10)),
                ("Stickhandling", getattr(self.player, 'stickhandling', 10))
            ]
            attributes.extend(winger_attrs)
            
        return attributes
    
    def _get_attribute_categories(self):
        """Organize attributes into logical categories."""
        categories = {
            "Technical": [],
            "Mental": [],
            "Physical": [],
            "Advanced": []
        }
        
        # Add position-specific category if needed
        pos = self.player.primary_position.name
        if pos == "G":
            categories["Goaltending"] = []
            
        # Map attributes to categories
        for attr_name in dir(self.player):
            if attr_name.startswith('_'):
                continue
                
            attr_value = getattr(self.player, attr_name)
            if not isinstance(attr_value, int) or not 1 <= attr_value <= 20:
                continue
                
            # Convert snake_case to Title Case
            display_name = ' '.join(word.capitalize() for word in attr_name.split('_'))
            
            # Categorize
            if attr_name in ['determination', 'teamwork', 'leadership', 'discipline', 
                           'flair', 'consistency', 'important_matches', 'morale',
                           'hockey_iq', 'composure', 'anticipation', 'decision_making',
                           'focus', 'confidence']:
                categories["Mental"].append((display_name, attr_value))
            elif attr_name in ['strength', 'speed', 'stamina', 'injury_proneness', 
                             'endurance', 'durability', 'acceleration', 'balance', 'agility']:
                categories["Physical"].append((display_name, attr_value))
            elif attr_name in ['reflexes', 'positioning', 'rebound_control', 'puck_handling',
                             'glove_hand', 'stick_side', 'breakaway_skill', 'goaltending']:
                if "Goaltending" in categories:
                    categories["Goaltending"].append((display_name, attr_value))
                else:
                    categories["Technical"].append((display_name, attr_value))
            elif attr_name in ['shooting_accuracy', 'shooting_power', 'passing_accuracy',
                             'passing_creativity', 'puck_protection', 'deflections',
                             'shot_blocking', 'aggressiveness', 'work_rate', 'vision']:
                categories["Advanced"].append((display_name, attr_value))
            else:
                categories["Technical"].append((display_name, attr_value))
                
        return categories
