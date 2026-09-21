# smart_data_widgets.py
# Smart data presentation widgets inspired by Football Manager and OOTP

import tkinter as tk
from tkinter import ttk
import math
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

@dataclass
class StatDisplay:
    """Configuration for displaying a stat with context"""
    label: str
    value: Any
    format_func: Optional[Callable] = None
    color_func: Optional[Callable] = None
    icon: Optional[str] = None
    subtitle: Optional[str] = None

class PlayerStatsCard(ttk.Frame):
    """Professional player stats card with visual hierarchy"""
    
    def __init__(self, parent, player, theme, **kwargs):
        super().__init__(parent, style='Card.TFrame', **kwargs)
        self.player = player
        self.theme = theme
        self.configure(padding=16)
        
        self._create_header()
        self._create_stats_grid()
        self._create_performance_indicators()
    
    def _create_header(self):
        """Create player header with photo placeholder and basic info"""
        header = ttk.Frame(self, style='Card.TFrame')
        header.pack(fill='x', pady=(0, 12))
        
        # Photo placeholder (colored circle with initials)
        photo_frame = tk.Frame(header, 
                              bg=self.theme.colors.primary_accent,
                              width=64, height=64)
        photo_frame.pack(side='left', padx=(0, 16))
        photo_frame.pack_propagate(False)
        
        initials = f"{self.player.first_name[0]}{self.player.last_name[0]}"
        photo_label = tk.Label(photo_frame,
                              text=initials,
                              bg=self.theme.colors.primary_accent,
                              fg='white',
                              font=self.theme.fonts['heading'])
        photo_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Player info
        info_frame = ttk.Frame(header, style='Card.TFrame')
        info_frame.pack(side='left', fill='both', expand=True)
        
        # Name
        name_label = ttk.Label(info_frame, 
                              text=self.player.full_name,
                              style='Heading.TLabel')
        name_label.pack(anchor='w')
        
        # Position and age
        details = f"{self.player.primary_position.value} • Age {self.player.age}"
        details_label = ttk.Label(info_frame,
                                 text=details,
                                 style='Subheading.TLabel')
        details_label.pack(anchor='w')
        
        # Overall rating with color
        ovr = self.player.overall_rating()
        ovr_color = self.theme.get_stat_color(ovr)
        ovr_frame = tk.Frame(info_frame, bg=self.theme.colors.tertiary_bg)
        ovr_frame.pack(anchor='w', pady=(4, 0))
        
        ovr_label = tk.Label(ovr_frame,
                            text=f"Overall: {ovr}",
                            bg=self.theme.colors.tertiary_bg,
                            fg=ovr_color,
                            font=self.theme.fonts['subheading'])
        ovr_label.pack(side='left')
    
    def _create_stats_grid(self):
        """Create organized stats grid with categories"""
        stats_frame = ttk.Frame(self, style='Card.TFrame')
        stats_frame.pack(fill='both', expand=True, pady=(12, 0))
        
        # Define stat categories
        stat_categories = self._get_position_specific_stats()
        
        row = 0
        for category, stats in stat_categories.items():
            # Category header
            category_label = ttk.Label(stats_frame,
                                     text=category.upper(),
                                     style='Subheading.TLabel')
            category_label.grid(row=row, column=0, columnspan=4, 
                               sticky='w', pady=(8 if row > 0 else 0, 4))
            row += 1
            
            # Stats in this category (2x2 grid)
            col = 0
            for stat in stats[:4]:  # Max 4 stats per category
                self._create_stat_display(stats_frame, stat, row, col)
                col += 1
                if col >= 2:  # 2 columns max
                    col = 0
                    row += 1
            if col > 0:  # If we ended mid-row
                row += 1
    
    def _create_stat_display(self, parent, stat: StatDisplay, row: int, col: int):
        """Create individual stat display with value and bar"""
        stat_frame = ttk.Frame(parent, style='Card.TFrame')
        stat_frame.grid(row=row, column=col, sticky='ew', padx=(0, 16), pady=2)
        
        # Stat label
        label = ttk.Label(stat_frame, text=stat.label, style='Muted.TLabel')
        label.pack(anchor='w')
        
        # Value with optional formatting
        value = stat.value
        if stat.format_func:
            value = stat.format_func(value)
        
        # Color coding
        color = self.theme.colors.secondary_text
        if stat.color_func:
            color = stat.color_func(stat.value)
        elif isinstance(stat.value, (int, float)):
            color = self.theme.get_stat_color(stat.value)
        
        value_label = tk.Label(stat_frame,
                              text=str(value),
                              bg=self.theme.colors.tertiary_bg,
                              fg=color,
                              font=self.theme.fonts['subheading'])
        value_label.pack(anchor='w')
        
        # Progress bar for numeric values
        if isinstance(stat.value, (int, float)) and stat.value <= 20:
            progress_frame = tk.Frame(stat_frame, height=4, bg=self.theme.colors.border_light)
            progress_frame.pack(fill='x', pady=(2, 0))
            progress_frame.pack_propagate(False)
            
            fill_width = int((stat.value / 20) * 100)  # Assuming 20 is max
            if fill_width > 0:
                progress_fill = tk.Frame(progress_frame, bg=color, height=4)
                progress_fill.place(x=0, y=0, relheight=1, width=f"{fill_width}%")
    
    def _get_position_specific_stats(self) -> Dict[str, List[StatDisplay]]:
        """Get relevant stats based on player position"""
        position = self.player.primary_position.value
        
        # Common stats for all positions
        common_stats = [
            StatDisplay("Overall", self.player.overall_rating()),
            StatDisplay("Skating", getattr(self.player, 'skating', 0)),
            StatDisplay("Determination", getattr(self.player, 'determination', 0)),
            StatDisplay("Teamwork", getattr(self.player, 'teamwork', 0)),
        ]
        
        if position == "G":  # Goalie
            return {
                "Core Attributes": common_stats,
                "Goaltending": [
                    StatDisplay("Goaltending", getattr(self.player, 'goaltending', 0)),
                    StatDisplay("Reflexes", getattr(self.player, 'reflexes', 0)),
                    StatDisplay("Positioning", getattr(self.player, 'positioning', 0)),
                    StatDisplay("Rebound Control", getattr(self.player, 'rebound_control', 0)),
                ]
            }
        else:  # Skaters
            offensive_stats = [
                StatDisplay("Shooting", getattr(self.player, 'shooting', 0)),
                StatDisplay("Passing", getattr(self.player, 'passing', 0)),
                StatDisplay("Offensive Awareness", getattr(self.player, 'offensive_awareness', 0)),
                StatDisplay("Deking", getattr(self.player, 'deking', 0)),
            ]
            
            defensive_stats = [
                StatDisplay("Checking", getattr(self.player, 'checking', 0)),
                StatDisplay("Defensive Awareness", getattr(self.player, 'defensive_awareness', 0)),
                StatDisplay("Shot Blocking", getattr(self.player, 'shot_blocking', 0)),
                StatDisplay("Faceoffs", getattr(self.player, 'faceoffs', 0)),
            ]
            
            return {
                "Core Attributes": common_stats,
                "Offensive": offensive_stats,
                "Defensive": defensive_stats,
            }
    
    def _create_performance_indicators(self):
        """Create performance trend indicators"""
        performance_frame = ttk.Frame(self, style='Card.TFrame')
        performance_frame.pack(fill='x', pady=(12, 0))
        
        ttk.Label(performance_frame,
                 text="SEASON PERFORMANCE",
                 style='Subheading.TLabel').pack(anchor='w')
        
        # Mock performance data - replace with actual stats
        indicators = [
            ("Goals", getattr(self.player.stats, 'goals', 0) if hasattr(self.player, 'stats') else 0),
            ("Assists", getattr(self.player.stats, 'assists', 0) if hasattr(self.player, 'stats') else 0),
            ("Plus/Minus", "+5"),  # Mock data
            ("Avg TOI", "18:23"),  # Mock data
        ]
        
        indicators_grid = ttk.Frame(performance_frame, style='Card.TFrame')
        indicators_grid.pack(fill='x', pady=(4, 0))
        
        for i, (label, value) in enumerate(indicators):
            indicator_frame = ttk.Frame(indicators_grid, style='Card.TFrame')
            indicator_frame.grid(row=0, column=i, sticky='ew', padx=(0, 16))
            
            ttk.Label(indicator_frame, text=label, style='Muted.TLabel').pack()
            
            value_label = ttk.Label(indicator_frame, text=str(value), style='Subheading.TLabel')
            value_label.pack()

class TeamStandingsWidget(ttk.Frame):
    """Professional team standings widget with visual enhancements"""
    
    def __init__(self, parent, standings_data, theme, user_team=None, **kwargs):
        super().__init__(parent, style='Card.TFrame', **kwargs)
        self.standings_data = standings_data
        self.theme = theme
        self.user_team = user_team
        self.configure(padding=16)
        
        self._create_header()
        self._create_standings_list()
    
    def _create_header(self):
        """Create standings header with division info"""
        header = ttk.Frame(self, style='Card.TFrame')
        header.pack(fill='x', pady=(0, 12))
        
        ttk.Label(header,
                 text="STANDINGS",
                 style='Heading.TLabel').pack(anchor='w')
        
        # Division filter buttons (mock)
        filter_frame = ttk.Frame(header, style='Card.TFrame')
        filter_frame.pack(anchor='w', pady=(8, 0))
        
        for division in ["Eastern", "Western", "Division"]:
            btn = ttk.Button(filter_frame, text=division, style='Secondary.TButton')
            btn.pack(side='left', padx=(0, 8))
    
    def _create_standings_list(self):
        """Create standings list with team positioning and trends"""
        standings_frame = ttk.Frame(self, style='Card.TFrame')
        standings_frame.pack(fill='both', expand=True)
        
        # Headers
        headers_frame = ttk.Frame(standings_frame, style='Card.TFrame')
        headers_frame.pack(fill='x', pady=(0, 8))
        
        headers = [("Team", 200), ("GP", 40), ("W", 40), ("L", 40), ("OTL", 40), ("PTS", 50), ("Trend", 60)]
        
        for i, (header, width) in enumerate(headers):
            label = ttk.Label(headers_frame, text=header, style='Subheading.TLabel')
            label.grid(row=0, column=i, sticky='w', padx=(0, 8))
        
        # Team rows with enhanced styling
        for pos, (team_name, record) in enumerate(self.standings_data.items(), 1):
            self._create_team_row(standings_frame, pos, team_name, record)
    
    def _create_team_row(self, parent, position: int, team_name: str, record: Dict):
        """Create individual team row with position indicator and trends"""
        row_frame = ttk.Frame(parent, style='Card.TFrame')
        row_frame.pack(fill='x', pady=1)
        
        # Highlight user team
        if team_name == self.user_team:
            row_frame.configure(style='Selected.TFrame')  # Would need to define this style
        
        # Position indicator
        pos_frame = tk.Frame(row_frame, width=30, height=24, 
                            bg=self._get_position_color(position))
        pos_frame.pack(side='left', padx=(0, 8))
        pos_frame.pack_propagate(False)
        
        pos_label = tk.Label(pos_frame, text=str(position),
                            bg=self._get_position_color(position),
                            fg='white',
                            font=self.theme.fonts['body'])
        pos_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Team name
        team_label = ttk.Label(row_frame, text=team_name, style='Body.TLabel')
        team_label.pack(side='left', padx=(0, 16))
        
        # Stats
        stats = [
            record.get('GP', 0),
            record.get('W', 0),
            record.get('L', 0),
            record.get('OTL', 0),
            record.get('Points', record.get('W', 0) * 2 + record.get('OTL', 0)),
        ]
        
        for stat in stats:
            stat_label = ttk.Label(row_frame, text=str(stat), style='Body.TLabel')
            stat_label.pack(side='left', padx=(0, 16))
        
        # Trend indicator (mock data)
        trend_text = "W2"  # Would be actual trend data
        trend_color = self.theme.colors.success
        trend_label = tk.Label(row_frame, text=trend_text,
                              bg=self.theme.colors.tertiary_bg,
                              fg=trend_color,
                              font=self.theme.fonts['small'])
        trend_label.pack(side='left')
    
    def _get_position_color(self, position: int) -> str:
        """Get color for position indicator"""
        if position <= 3:
            return self.theme.colors.success  # Playoff position
        elif position <= 8:
            return self.theme.colors.warning  # Wild card
        else:
            return self.theme.colors.muted_text  # Out of playoffs

class StatComparisonWidget(ttk.Frame):
    """Professional stat comparison widget for player analysis"""
    
    def __init__(self, parent, players: List, stat_name: str, theme, **kwargs):
        super().__init__(parent, style='Card.TFrame', **kwargs)
        self.players = players
        self.stat_name = stat_name
        self.theme = theme
        self.configure(padding=16)
        
        self._create_comparison_chart()
    
    def _create_comparison_chart(self):
        """Create horizontal bar chart for stat comparison"""
        header = ttk.Label(self, text=f"{self.stat_name.upper()} COMPARISON", 
                          style='Heading.TLabel')
        header.pack(anchor='w', pady=(0, 12))
        
        if not self.players:
            return
        
        # Get max value for scaling
        max_value = max(getattr(player, self.stat_name.lower(), 0) for player in self.players)
        if max_value == 0:
            max_value = 1
        
        for player in self.players[:5]:  # Show top 5
            self._create_player_comparison_bar(player, max_value)
    
    def _create_player_comparison_bar(self, player, max_value: float):
        """Create individual player comparison bar"""
        player_frame = ttk.Frame(self, style='Card.TFrame')
        player_frame.pack(fill='x', pady=4)
        
        # Player name
        name_label = ttk.Label(player_frame, text=player.full_name, style='Body.TLabel')
        name_label.pack(anchor='w')
        
        # Bar container
        bar_container = tk.Frame(player_frame, height=20, bg=self.theme.colors.border_light)
        bar_container.pack(fill='x', pady=(2, 4))
        bar_container.pack_propagate(False)
        
        # Stat value
        stat_value = getattr(player, self.stat_name.lower(), 0)
        bar_width = (stat_value / max_value) * 100
        
        if bar_width > 0:
            # Colored bar
            color = self.theme.get_stat_color(stat_value, max_value)
            bar_fill = tk.Frame(bar_container, bg=color, height=20)
            bar_fill.place(x=0, y=0, relheight=1, width=f"{bar_width}%")
        
        # Value label
        value_label = tk.Label(bar_container, text=str(stat_value),
                              bg=self.theme.colors.border_light,
                              fg=self.theme.colors.primary_text,
                              font=self.theme.fonts['small'])
        value_label.place(relx=1, rely=0.5, anchor='e', x=-4)
