"""
Enhanced Stats and Standings Window for Hockey Manager
Comprehensive view with advanced analytics, historical data, and interactive features
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta

# Import our advanced analytics system
try:
    from advanced_stats_analytics import RealTimeStatsEngine, PlayerStats, TeamStats
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    print("Warning: Advanced analytics system not available, using fallback data")

class StatsStandingsWindow(tk.Toplevel):
    """Advanced Stats and Standings window with deep analytics and multiple view modes"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Advanced League Analytics & Standings - Hockey Manager")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1600x1000")
        self.minsize(1400, 800)
        
        # Enhanced state tracking
        self.selected_tab = 0
        self.historical_data = {}
        self.analytics_cache = {}
        self.filters = {
            'time_period': 'Season',
            'team_filter': 'All Teams',
            'stat_type': 'Overall'
        }
        
        # Initialize analytics engine if available
        self.analytics_engine = None
        if ANALYTICS_AVAILABLE:
            self.analytics_engine = RealTimeStatsEngine()
            self._initialize_analytics_from_game_data()
        
        # Create the enhanced interface
        self.create_interface()
        
        # Track window
        self.parent.open_windows['stats_standings'] = self
        
    def _initialize_analytics_from_game_data(self):
        """Initialize analytics engine with current game data"""
        try:
            if not self.parent.game_manager or not self.parent.game_manager.league:
                return
                
            # Find NHL teams
            nhl_teams = []
            if hasattr(self.parent.game_manager.league, 'teams'):
                nhl_teams = self.parent.game_manager.league.teams
            elif hasattr(self.parent.game_manager.league, 'leagues'):
                for league in self.parent.game_manager.league.leagues:
                    if hasattr(league, 'name') and "National Hockey League" in league.name:
                        nhl_teams = league.teams
                        break
            
            if not nhl_teams:
                return
                
            # Initialize analytics for each team
            for team in nhl_teams:
                if hasattr(team, 'roster') and team.roster:
                    # Convert team data to analytics format
                    home_players = []
                    for player in team.roster:
                        home_players.append({
                            'id': f"{team.team_name}_{getattr(player, 'full_name', 'Unknown')}",
                            'name': getattr(player, 'full_name', 'Unknown'),
                            'position': getattr(player, 'primary_position', 'C')
                        })
                    
                    # Initialize analytics (this would normally be done at game start)
                    if len(home_players) > 0:
                        self.analytics_engine.initialize_game(
                            team.team_name, 
                            "TBD",  # Actual opponent will be determined from schedule data
                            home_players, 
                            []  # Away players would be empty for this initialization
                        )
                        
                        # Populate with existing player stats if available
                        for player in team.roster:
                            player_id = f"{team.team_name}_{getattr(player, 'full_name', 'Unknown')}"
                            if player_id in self.analytics_engine.player_stats:
                                stats = self.analytics_engine.player_stats[player_id]
                                # Update with real data from player object
                                stats.goals = getattr(player, 'goals', 0)
                                stats.assists = getattr(player, 'assists', 0)
                                stats.shots = getattr(player, 'shots', 0)
                                stats.hits = getattr(player, 'hits', 0)
                                stats.blocks = getattr(player, 'blocks', 0)
                                stats.ice_time = getattr(player, 'ice_time', 0.0)
                        
                        # Update team stats
                        if team.team_name in self.analytics_engine.team_stats:
                            team_stats = self.analytics_engine.team_stats[team.team_name]
                            team_stats.goals = getattr(team, 'goals_for', 0)
                            team_stats.shots = getattr(team, 'shots_for', 0)
                            team_stats.hits = getattr(team, 'hits_for', 0)
                            
        except Exception as e:
            print(f"Warning: Could not initialize analytics from game data: {e}")
    
    def set_focus_tab(self, tab_name):
        """Set focus to a specific tab - for external navigation"""
        tab_map = {
            'standings': 0,
            'team_stats': 1,
            'player_leaders': 2,
            'analytics': 3,
            'divisions': 4
        }
        if tab_name in tab_map:
            self.notebook.select(tab_map[tab_name])
    
    def create_interface(self):
        """Create the enhanced interface with advanced features"""
        # Main container with enhanced styling
        main_frame = ttk.Frame(self, style='Panel.TFrame', padding=15)
        main_frame.pack(fill='both', expand=True)
        
        # Enhanced title bar with analytics indicators
        title_frame = ttk.Frame(main_frame, style='TitleBar.TFrame', padding=15)
        title_frame.pack(fill='x', pady=(0, 15))
        
        # Title with live update indicator
        title_container = ttk.Frame(title_frame, style='TitleBar.TFrame')
        title_container.pack(side='left', fill='x', expand=True)
        
        title_label = ttk.Label(title_container, text="Advanced League Analytics & Standings", 
                               style='Title.TLabel')
        title_label.pack(side='left')
        
        # Live data indicator
        self.live_indicator = ttk.Label(title_container, text="🟢 LIVE", 
                                       style='Success.TLabel', font=('Segoe UI', 9, 'bold'))
        self.live_indicator.pack(side='left', padx=(10, 0))
        
        # Global filters
        filters_frame = ttk.Frame(title_frame, style='TitleBar.TFrame')
        filters_frame.pack(side='right', padx=(10, 0))
        
        ttk.Label(filters_frame, text="Period:", style='TLabel').pack(side='left', padx=(0, 5))
        self.period_var = tk.StringVar(value="Season")
        period_combo = ttk.Combobox(filters_frame, textvariable=self.period_var,
                                   values=["Last 10 Games", "Last Month", "Season", "All Time"],
                                   state="readonly", width=12)
        period_combo.pack(side='left', padx=(0, 10))
        period_combo.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        # Close button
        close_btn = ttk.Button(filters_frame, text="✕ Close", style='TButton',
                              command=self.destroy)
        close_btn.pack(side='left', padx=(10, 0))
        
        # Create enhanced notebook with more tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Create enhanced tabs (streamlined and organized)
        self.create_enhanced_standings_tab()
        self.create_advanced_team_stats_tab()
        self.create_enhanced_player_leaders_tab()
        self.create_comprehensive_analytics_tab()  # Combines analytics, trends, and insights
        self.create_division_analysis_tab()
        
        # Enhanced status bar
        status_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        status_frame.pack(fill='x')
        
        # Refresh controls
        refresh_frame = ttk.Frame(status_frame, style='Panel.TFrame')
        refresh_frame.pack(side='right')
        
        ttk.Button(refresh_frame, text="🔄 Refresh All", style='TButton',
                  command=self.refresh_all_data).pack(side='right', padx=5)
        
        ttk.Button(refresh_frame, text="📊 Export Data", style='TButton',
                  command=self.export_data).pack(side='right', padx=5)
        
        # Status info
        status_info = ttk.Frame(status_frame, style='Panel.TFrame')
        status_info.pack(side='left', fill='x', expand=True)
        
        self.status_label = ttk.Label(status_info, text="✅ Ready - Real game data loaded successfully", 
                                     style='Muted.TLabel')
        self.status_label.pack(side='left')
        
        # Data summary
        self.data_summary_label = ttk.Label(status_info, text="", 
                                           style='Muted.TLabel')
        self.data_summary_label.pack(side='left', padx=(20, 0))
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Update data summary
        self.update_data_summary()
    
    def update_data_summary(self):
        """Update the data summary in the status bar"""
        try:
            league = getattr(self.parent.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                team_count = len(league.teams)
                # Count total players
                total_players = 0
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        total_players += len(team.roster)
                
                summary = f"📊 {team_count} teams • {total_players:,} players • Analytics: {'✅ Active' if self.analytics_engine else '❌ Unavailable'}"
                self.data_summary_label.config(text=summary)
            else:
                self.data_summary_label.config(text="⚠️ No league data available")
        except Exception as e:
            self.data_summary_label.config(text=f"❌ Data error: {str(e)}")
    
    def create_enhanced_standings_tab(self):
        """Create enhanced standings tab with playoff race and momentum indicators"""
        standings_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(standings_frame, text="🏆 Standings")
        
        # Enhanced controls with more options
        controls_frame = ttk.Frame(standings_frame, style='Panel.TFrame')
        controls_frame.pack(fill='x', pady=(0, 15))
        
        # View options
        ttk.Label(controls_frame, text="View:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.standings_view = tk.StringVar(value="League Overview")
        view_combo = ttk.Combobox(controls_frame, textvariable=self.standings_view,
                                 values=["League Overview", "Eastern Conference", "Western Conference", 
                                        "Wild Card Race", "Division Leaders", "Playoff Picture"],
                                 state="readonly", width=20)
        view_combo.pack(side='left', padx=(0, 15))
        view_combo.bind('<<ComboboxSelected>>', self.update_standings_view)
        
        # Sort options
        ttk.Label(controls_frame, text="Sort by:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.standings_sort = tk.StringVar(value="Points")
        sort_combo = ttk.Combobox(controls_frame, textvariable=self.standings_sort,
                                 values=["Points", "Wins", "Goal Differential", "Recent Form", "Home Record", "Road Record"],
                                 state="readonly", width=15)
        sort_combo.pack(side='left', padx=(0, 15))
        sort_combo.bind('<<ComboboxSelected>>', self.update_standings_view)
        
        # Toggle advanced metrics
        self.show_advanced = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls_frame, text="Advanced Metrics", variable=self.show_advanced,
                       command=self.update_standings_view).pack(side='left', padx=(0, 10))
        
        # Main standings area with scrolling
        standings_container = ttk.Frame(standings_frame, style='Panel.TFrame')
        standings_container.pack(fill='both', expand=True)
        
        # Create scrollable area
        canvas = tk.Canvas(standings_container, bg=self.parent.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(standings_container, orient="vertical", command=canvas.yview)
        self.standings_scrollable = ttk.Frame(canvas, style='Panel.TFrame')
        
        self.standings_scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.standings_scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.standings_canvas = canvas
        self.populate_enhanced_standings()
    
    def create_advanced_team_stats_tab(self):
        """Create advanced team statistics with comparative analysis"""
        stats_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(stats_frame, text="📊 Team Analytics")
        
        # Advanced controls
        controls_frame = ttk.Frame(stats_frame, style='Panel.TFrame')
        controls_frame.pack(fill='x', pady=(0, 15))
        
        # Category selection with more options
        ttk.Label(controls_frame, text="Category:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.stats_category = tk.StringVar(value="Overall Performance")
        category_combo = ttk.Combobox(controls_frame, textvariable=self.stats_category,
                                     values=["Overall Performance", "Offensive Stats", "Defensive Stats", 
                                            "Special Teams", "Goaltending", "Advanced Analytics", 
                                            "Situational Stats", "Home vs Road"],
                                     state="readonly", width=20)
        category_combo.pack(side='left', padx=(0, 15))
        category_combo.bind('<<ComboboxSelected>>', self.update_team_stats_view)
        
        # Comparison mode
        ttk.Label(controls_frame, text="View Mode:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.stats_mode = tk.StringVar(value="League Rankings")
        mode_combo = ttk.Combobox(controls_frame, textvariable=self.stats_mode,
                                 values=["League Rankings", "vs League Average", "Trend Analysis", "Head-to-Head"],
                                 state="readonly", width=15)
        mode_combo.pack(side='left', padx=(0, 15))
        mode_combo.bind('<<ComboboxSelected>>', self.update_team_stats_view)
        
        # Team filter
        ttk.Label(controls_frame, text="Teams:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.team_filter = tk.StringVar(value="All Teams")
        team_combo = ttk.Combobox(controls_frame, textvariable=self.team_filter,
                                 values=["All Teams", "Eastern Conference", "Western Conference", 
                                        "Division Rivals", "Playoff Teams"],
                                 state="readonly", width=15)
        team_combo.pack(side='left')
        team_combo.bind('<<ComboboxSelected>>', self.update_team_stats_view)
        
        # Stats display area
        self.team_stats_container = ttk.Frame(stats_frame, style='Panel.TFrame')
        self.team_stats_container.pack(fill='both', expand=True)
        
        self.populate_advanced_team_stats()
    
    def create_enhanced_player_leaders_tab(self):
        """Create enhanced player leaders with advanced filtering"""
        leaders_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(leaders_frame, text="⭐ Player Leaders")
        
        # Enhanced controls
        controls_frame = ttk.Frame(leaders_frame, style='Panel.TFrame')
        controls_frame.pack(fill='x', pady=(0, 15))
        
        # Position filter
        ttk.Label(controls_frame, text="Position:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.position_filter = tk.StringVar(value="All Positions")
        pos_combo = ttk.Combobox(controls_frame, textvariable=self.position_filter,
                                values=["All Positions", "Forwards", "Defensemen", "Goalies", 
                                       "Centers", "Wingers", "Rookies", "Veterans"],
                                state="readonly", width=15)
        pos_combo.pack(side='left', padx=(0, 15))
        pos_combo.bind('<<ComboboxSelected>>', self.update_player_leaders)
        
        # Minimum games filter
        ttk.Label(controls_frame, text="Min Games:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.min_games = tk.IntVar(value=10)
        games_spin = tk.Spinbox(controls_frame, from_=1, to=82, textvariable=self.min_games,
                               width=5, command=self.update_player_leaders)
        games_spin.pack(side='left', padx=(0, 15))
        
        # Show per-game stats
        self.show_per_game = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls_frame, text="Per Game Stats", variable=self.show_per_game,
                       command=self.update_player_leaders).pack(side='left')
        
        # Create enhanced sub-tabs
        self.leaders_notebook = ttk.Notebook(leaders_frame)
        self.leaders_notebook.pack(fill='both', expand=True)
        
        # Enhanced scoring leaders
        scoring_frame = ttk.Frame(self.leaders_notebook, style='Panel.TFrame', padding=10)
        self.leaders_notebook.add(scoring_frame, text="Scoring Leaders")
        self.create_enhanced_player_section(scoring_frame, "scoring")
        
        # Advanced stats
        advanced_frame = ttk.Frame(self.leaders_notebook, style='Panel.TFrame', padding=10)
        self.leaders_notebook.add(advanced_frame, text="Advanced Stats")
        self.create_enhanced_player_section(advanced_frame, "advanced")
        
        # Goalie leaders with more depth
        goalie_frame = ttk.Frame(self.leaders_notebook, style='Panel.TFrame', padding=10)
        self.leaders_notebook.add(goalie_frame, text="Goaltending")
        self.create_enhanced_player_section(goalie_frame, "goaltending")
        
        # Breakout players
        breakout_frame = ttk.Frame(self.leaders_notebook, style='Panel.TFrame', padding=10)
        self.leaders_notebook.add(breakout_frame, text="Breakout Players")
        self.create_enhanced_player_section(breakout_frame, "breakout")
        
        # Records section - accessible from player leaders
        records_frame = ttk.Frame(self.leaders_notebook, style='Panel.TFrame', padding=10)
        self.leaders_notebook.add(records_frame, text="🏆 NHL Records")
        self.create_records_section(records_frame)
    
    def create_records_section(self, parent_frame):
        """Create records section within player leaders tab"""
        # Records notebook for different categories
        self.records_notebook = ttk.Notebook(parent_frame)
        self.records_notebook.pack(fill='both', expand=True)
        
        # Create record category tabs
        self._create_season_records_tab()
        self._create_career_records_tab()
        self._create_current_leaders_tab()
        self._create_record_chase_tab()
        self._create_achievements_tab()
    
    def create_comprehensive_analytics_tab(self):
        """Create comprehensive analytics tab combining analytics, trends, and insights"""
        analytics_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(analytics_frame, text="📈 Analytics & Trends")
        
        # Create sub-notebook for different analytics views
        self.analytics_notebook = ttk.Notebook(analytics_frame)
        self.analytics_notebook.pack(fill='both', expand=True)
        
        # Analytics Dashboard
        dashboard_frame = ttk.Frame(self.analytics_notebook, style='Panel.TFrame', padding=10)
        self.analytics_notebook.add(dashboard_frame, text="📊 Dashboard")
        self.create_analytics_dashboard_content(dashboard_frame)
        
        # Trends Analysis
        trends_frame = ttk.Frame(self.analytics_notebook, style='Panel.TFrame', padding=10)
        self.analytics_notebook.add(trends_frame, text="📈 Trends")
        self.create_trends_analysis_content(trends_frame)
        
        # Performance Insights
        insights_frame = ttk.Frame(self.analytics_notebook, style='Panel.TFrame', padding=10)
        self.analytics_notebook.add(insights_frame, text="🎯 Insights")
        self.create_performance_insights_content(insights_frame)
    
    def create_records_tab(self):
        """Create NHL Records tab with comprehensive record tracking"""
        records_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=15)
        self.notebook.add(records_frame, text="🏆 NHL Records")
        
        # Professional header
        header_frame = ttk.Frame(records_frame, style='Panel.TFrame')
        header_frame.pack(fill='x', pady=(0, 20))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title and description
        title_container = ttk.Frame(header_frame, style='Panel.TFrame')
        title_container.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(title_container, text="🏆 NHL Records & Achievements", 
                               font=(self.parent.FONT_FAMILY, 16, 'bold'),
                               foreground='#FFFFFF', background=self.parent.BG_COLOR)
        title_label.pack(anchor='w')
        
        desc_label = ttk.Label(title_container, text="Track legendary performances and chase greatness",
                              font=(self.parent.FONT_FAMILY, 10),
                              foreground='#B0B0B0', background=self.parent.BG_COLOR)
        desc_label.pack(anchor='w', pady=(3, 0))
        
        # Stats summary
        stats_frame = ttk.Frame(header_frame, style='Panel.TFrame')
        stats_frame.grid(row=0, column=2, sticky="e")
        
        try:
            record_manager = self.parent.game_manager.record_manager
            total_records = len(record_manager.nhl_records.season_records) + len(record_manager.nhl_records.career_records)
            stats_text = f"📊 {total_records} Official NHL Records"
            if hasattr(record_manager, 'achievements') and record_manager.achievements:
                stats_text += f" • 🎯 {len(record_manager.achievements)} Achievements"
        except:
            stats_text = "📊 Official NHL Records Database"
            
        stats_label = ttk.Label(stats_frame, text=stats_text,
                               font=(self.parent.FONT_FAMILY, 9),
                               foreground='#888888', background=self.parent.BG_COLOR)
        stats_label.pack(anchor='e')
        
        # Enhanced toolbar
        toolbar_frame = ttk.Frame(records_frame, style='Panel.TFrame')
        toolbar_frame.pack(fill='x', pady=(0, 15))
        toolbar_frame.grid_columnconfigure(1, weight=1)
        
        # Search functionality
        search_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        search_container.grid(row=0, column=0, sticky="w")
        
        ttk.Label(search_container, text="🔍 Search:", 
                 font=(self.parent.FONT_FAMILY, 9), foreground=self.parent.TEXT_COLOR,
                 background=self.parent.BG_COLOR).pack(side='left', padx=(0, 5))
        
        self.records_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_container, textvariable=self.records_search_var,
                                font=(self.parent.FONT_FAMILY, 9), width=25)
        search_entry.pack(side='left', padx=(0, 20))
        
        # Category filter
        filter_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        filter_container.grid(row=0, column=1, sticky="")
        
        ttk.Label(filter_container, text="📂 Category:",
                 font=(self.parent.FONT_FAMILY, 9), foreground=self.parent.TEXT_COLOR,
                 background=self.parent.BG_COLOR).pack(side='left', padx=(0, 5))
        
        self.records_filter_var = tk.StringVar(value="All Records")
        filter_combo = ttk.Combobox(filter_container, textvariable=self.records_filter_var,
                                   values=["All Records", "Scoring", "Goaltending", "Team Records"],
                                   state="readonly", font=(self.parent.FONT_FAMILY, 9), width=15)
        filter_combo.pack(side='left')
        
        # Refresh button
        refresh_container = ttk.Frame(toolbar_frame, style='Panel.TFrame')
        refresh_container.grid(row=0, column=2, sticky="e")
        
        refresh_btn = ttk.Button(refresh_container, text="🔄 Refresh",
                                style='TButton', command=self.refresh_records_data)
        refresh_btn.pack(side='left')
        
        # Records notebook for different categories
        self.records_notebook = ttk.Notebook(records_frame)
        self.records_notebook.pack(fill='both', expand=True)
        
        # Create record category tabs
        self._create_season_records_tab()
        self._create_career_records_tab()
        self._create_current_leaders_tab()
        self._create_record_chase_tab()
        self._create_achievements_tab()
        
    def _create_season_records_tab(self):
        """Create season records tab"""
        season_frame = ttk.Frame(self.records_notebook, style='Panel.TFrame', padding=10)
        self.records_notebook.add(season_frame, text="🏒 Season Records")
        
        # Create scrollable frame
        canvas = tk.Canvas(season_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(season_frame, orient="vertical", command=canvas.yview)
        self.season_scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        self.season_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.season_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate with season records
        self._populate_season_records()
        
    def _create_career_records_tab(self):
        """Create career records tab"""
        career_frame = ttk.Frame(self.records_notebook, style='Panel.TFrame', padding=10)
        self.records_notebook.add(career_frame, text="🎯 Career Records")
        
        # Create scrollable frame
        canvas = tk.Canvas(career_frame, bg=self.parent.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(career_frame, orient="vertical", command=canvas.yview)
        self.career_scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        self.career_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.career_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate with career records
        self._populate_career_records()
        
    def _create_current_leaders_tab(self):
        """Create current season leaders tab"""
        leaders_frame = ttk.Frame(self.records_notebook, style='Panel.TFrame', padding=10)
        self.records_notebook.add(leaders_frame, text="⭐ Current Leaders")
        
        # Create treeview for current leaders
        columns = {
            'rank': ('Rank', 50),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'position': ('Pos', 60),
            'stat': ('Stat', 100),
            'value': ('Value', 80)
        }
        
        self.current_leaders_tree = self.parent._create_treeview(leaders_frame, columns, height=20)
        
        # Populate with current season leaders
        self._populate_current_leaders()
        
    def _create_record_chase_tab(self):
        """Create record chase tracking tab"""
        chase_frame = ttk.Frame(self.records_notebook, style='Panel.TFrame', padding=10)
        self.records_notebook.add(chase_frame, text="🏃 Record Chase")
        
        # Header with explanation
        header_frame = ttk.Frame(chase_frame, style='Panel.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))
        
        explanation_label = ttk.Label(header_frame,
                                     text="Players currently chasing NHL records (25%+ progress toward record)",
                                     font=(self.parent.FONT_FAMILY, 10),
                                     foreground='#B0B0B0',
                                     background=self.parent.BG_COLOR)
        explanation_label.pack(anchor='w')
        
        # Create treeview for record chase
        columns = {
            'rank': ('Rank', 50),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'position': ('Pos', 60),
            'record': ('Record', 100),
            'current': ('Current', 80),
            'target': ('Target', 80),
            'needed': ('Needed', 80),
            'progress': ('Progress', 80)
        }
        
        self.record_chase_tree = self.parent._create_treeview(chase_frame, columns, height=18)
        
        # Populate with record chase data
        self._populate_record_chase()
        
    def _create_achievements_tab(self):
        """Create achievements and recent records tab"""
        achievements_frame = ttk.Frame(self.records_notebook, style='Panel.TFrame', padding=10)
        self.records_notebook.add(achievements_frame, text="🏅 Achievements")
        
        # Create treeview for achievements
        columns = {
            'date': ('Date', 100),
            'player': ('Player', 180),
            'team': ('Team', 120),
            'record': ('Record', 200),
            'value': ('New Value', 100),
            'previous': ('Previous', 100)
        }
        
        self.achievements_tree = self.parent._create_treeview(achievements_frame, columns, height=20)
        
        # Populate with achievements
        self._populate_achievements()
    
    def create_analytics_dashboard_tab(self):
        """Create advanced analytics dashboard"""
        analytics_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(analytics_frame, text="📈 Analytics")
        
        # Dashboard grid
        analytics_frame.grid_rowconfigure(0, weight=1)
        analytics_frame.grid_rowconfigure(1, weight=1)
        analytics_frame.grid_columnconfigure(0, weight=1)
        analytics_frame.grid_columnconfigure(1, weight=1)
        
        # Top left: League trends
        trends_panel = self.create_analytics_panel(analytics_frame, "League Trends", 0, 0)
        self.populate_trends_panel(trends_panel)
        
        # Top right: Statistical outliers
        outliers_panel = self.create_analytics_panel(analytics_frame, "Statistical Outliers", 0, 1)
        self.populate_outliers_panel(outliers_panel)
        
        # Bottom left: Performance predictors
        predictors_panel = self.create_analytics_panel(analytics_frame, "Performance Indicators", 1, 0)
        self.populate_predictors_panel(predictors_panel)
        
        # Bottom right: Advanced metrics
        metrics_panel = self.create_analytics_panel(analytics_frame, "Advanced Metrics", 1, 1)
        self.populate_metrics_panel(metrics_panel)
    
    def create_trends_analysis_tab(self):
        """Create trends and momentum analysis tab"""
        trends_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(trends_frame, text="📈 Trends")
        
        # Time period selector
        period_frame = ttk.Frame(trends_frame, style='Panel.TFrame')
        period_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(period_frame, text="Analysis Period:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.trend_period = tk.StringVar(value="Last 20 Games")
        period_combo = ttk.Combobox(period_frame, textvariable=self.trend_period,
                                   values=["Last 10 Games", "Last 20 Games", "Last Month", "Season"],
                                   state="readonly", width=15)
        period_combo.pack(side='left', padx=(0, 15))
        period_combo.bind('<<ComboboxSelected>>', self.update_trends_analysis)
        
        # Main trends display
        self.trends_container = ttk.Frame(trends_frame, style='Panel.TFrame')
        self.trends_container.pack(fill='both', expand=True)
        
        self.populate_trends_analysis()
    
    def create_division_analysis_tab(self):
        """Create enhanced division analysis tab"""
        division_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(division_frame, text="🏛️ Division Analysis")
        
        # Division selector
        div_controls = ttk.Frame(division_frame, style='Panel.TFrame')
        div_controls.pack(fill='x', pady=(0, 15))
        
        ttk.Label(div_controls, text="Division:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.division_view = tk.StringVar(value="All Divisions")
        div_combo = ttk.Combobox(div_controls, textvariable=self.division_view,
                                values=["All Divisions", "Atlantic", "Metropolitan", "Central", "Pacific"],
                                state="readonly", width=15)
        div_combo.pack(side='left', padx=(0, 15))
        div_combo.bind('<<ComboboxSelected>>', self.update_division_analysis)
        
        # Analysis type
        ttk.Label(div_controls, text="Analysis:", style='TLabel').pack(side='left', padx=(0, 5))
        
        self.div_analysis_type = tk.StringVar(value="Standings")
        analysis_combo = ttk.Combobox(div_controls, textvariable=self.div_analysis_type,
                                     values=["Standings", "Head-to-Head", "Strength of Schedule", "Division vs League"],
                                     state="readonly", width=20)
        analysis_combo.pack(side='left')
        analysis_combo.bind('<<ComboboxSelected>>', self.update_division_analysis)
        
        # Division analysis display
        self.division_container = ttk.Frame(division_frame, style='Panel.TFrame')
        self.division_container.pack(fill='both', expand=True)
        
        self.populate_division_analysis()
        division_frame = ttk.Frame(self.notebook, style='Panel.TFrame', padding=10)
        self.notebook.add(division_frame, text="🏒 Divisions")
        
        # Create a grid layout for all 4 divisions
        self.create_division_grid(division_frame)
    
    def populate_standings(self):
        """Populate the standings with current data"""
        # Clear existing content
        for widget in self.standings_container.winfo_children():
            widget.destroy()
        
        # Get standings data from the dashboard system
        try:
            if hasattr(self.parent, 'atmospheric_dashboard'):
                standings_data = self.parent.atmospheric_dashboard._get_standings_data()
            else:
                standings_data = self.get_standings_data()
            
            # Create standings tables
            if self.standings_view.get() == "Both Conferences":
                self.create_conference_standings(self.standings_container, standings_data)
            else:
                selected_conf = self.standings_view.get()
                filtered_data = {k: v for k, v in standings_data.items() if selected_conf.split()[0] in k}
                self.create_conference_standings(self.standings_container, filtered_data)
                
        except Exception as e:
            error_label = ttk.Label(self.standings_container, 
                                   text=f"Error loading standings: {e}", 
                                   style='TLabel')
            error_label.pack(pady=20)
    
    def create_conference_standings(self, parent, standings_data):
        """Create standings tables for conferences/divisions"""
        # Create scrollable frame
        canvas = tk.Canvas(parent, bg=self.parent.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Panel.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create standings for each division/conference
        row = 0
        for division_name, teams in standings_data.items():
            # Division header
            division_label = ttk.Label(scrollable_frame, text=division_name, 
                                     style='Heading.TLabel')
            division_label.grid(row=row, column=0, columnspan=8, sticky='w', pady=(10, 5), padx=10)
            row += 1
            
            # Column headers
            headers = ['Rank', 'Team', 'GP', 'W', 'L', 'T', 'PTS', 'PCT']
            for col, header in enumerate(headers):
                header_label = ttk.Label(scrollable_frame, text=header, style='Subheading.TLabel')
                header_label.grid(row=row, column=col, sticky='w', padx=5, pady=2)
            row += 1
            
            # Team data
            for rank, team in enumerate(teams, 1):
                # Highlight user team
                style = 'Title.TLabel' if team['name'] == getattr(self.parent, 'user_team', {}).get('team_name', '') else 'TLabel'
                
                ttk.Label(scrollable_frame, text=str(rank), style=style).grid(row=row, column=0, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=team['name'], style=style).grid(row=row, column=1, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['games_played']), style=style).grid(row=row, column=2, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['wins']), style=style).grid(row=row, column=3, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['losses']), style=style).grid(row=row, column=4, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['ties']), style=style).grid(row=row, column=5, sticky='w', padx=5)
                ttk.Label(scrollable_frame, text=str(team['points']), style=style).grid(row=row, column=6, sticky='w', padx=5)
                
                # Calculate winning percentage
                pct = team['points'] / (team['games_played'] * 2) if team['games_played'] > 0 else 0
                ttk.Label(scrollable_frame, text=f"{pct:.3f}", style=style).grid(row=row, column=7, sticky='w', padx=5)
                row += 1
            
            row += 1  # Add space between divisions
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def populate_team_stats(self):
        """Populate team statistics based on selected category"""
        # Clear existing content
        for widget in self.team_stats_container.winfo_children():
            widget.destroy()
        
        category = self.stats_category.get()
        
        # Create team stats table
        columns = self.get_team_stats_columns(category)
        
        # Create treeview
        tree = ttk.Treeview(self.team_stats_container, columns=list(columns.keys()), 
                           show='headings', height=20)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='w')
            tree.column(col_id, width=width, anchor='w')
        
        # Use real data instead of sample data
        self.populate_team_stats_data(tree, category)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.team_stats_container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_player_leaders_section(self, parent, category):
        """Create a player leaders section for the given category"""
        columns = self.get_player_leaders_columns(category)
        
        # Create treeview
        tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                           show='headings', height=15)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='w')
            tree.column(col_id, width=width, anchor='w')
        
        # Use real data instead of sample data
        self.populate_player_leaders_data(tree, category)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_division_grid(self, parent):
        """Create a 2x2 grid showing all 4 NHL divisions"""
        # Main grid frame
        grid_frame = ttk.Frame(parent, style='Panel.TFrame')
        grid_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        
        # Eastern Conference divisions
        self.create_division_panel(grid_frame, "Eastern - Atlantic", 0, 0)
        self.create_division_panel(grid_frame, "Eastern - Metropolitan", 0, 1)
        
        # Western Conference divisions  
        self.create_division_panel(grid_frame, "Western - Central", 1, 0)
        self.create_division_panel(grid_frame, "Western - Pacific", 1, 1)
    
    def create_division_panel(self, parent, division_name, row, col):
        """Create a panel for a single division"""
        # Panel frame
        panel = ttk.LabelFrame(parent, text=division_name, style='Card.TFrame', padding=10)
        panel.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
        
        # Get division data
        standings_data = self.get_standings_data()
        division_teams = standings_data.get(division_name, [])
        
        # Create mini standings table
        for i, team in enumerate(division_teams[:8]):  # Limit to 8 teams per division
            # Team rank and name
            rank_label = ttk.Label(panel, text=f"{i+1}.", style='TLabel')
            rank_label.grid(row=i, column=0, sticky='w', padx=(0, 5))
            
            team_label = ttk.Label(panel, text=team['name'][:20], style='TLabel')
            team_label.grid(row=i, column=1, sticky='w', padx=(0, 10))
            
            # Record
            record_label = ttk.Label(panel, text=team['record'], style='TLabel')
            record_label.grid(row=i, column=2, sticky='w', padx=(0, 5))
            
            # Points
            points_label = ttk.Label(panel, text=f"{team['points']}pts", style='TLabel')
            points_label.grid(row=i, column=3, sticky='e')
    
    def get_standings_data(self):
        """Get standings data from the parent application"""
        try:
            # Try to get data from the atmospheric dashboard
            if hasattr(self.parent, 'atmospheric_dashboard'):
                return self.parent.atmospheric_dashboard._get_standings_data()
            else:
                # Fallback: get data directly from league
                return self.get_league_standings()
        except Exception as e:
            print(f"Error getting standings data: {e}")
            return self.get_fallback_standings()
    
    def get_league_standings(self):
        """Get standings directly from league data"""
        if not hasattr(self.parent, 'league') or not self.parent.league:
            return self.get_fallback_standings()
        
        # Get NHL teams
        nhl_teams = [team for team in self.parent.league.teams 
                    if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
        
        if not nhl_teams:
            nhl_teams = self.parent.league.teams[:32]  # Assume first 32 are NHL
        
        # Group by division
        divisions = {}
        for team in nhl_teams:
            if hasattr(team, 'division') and hasattr(team, 'conference'):
                division_name = f"{team.conference} - {team.division}"
            elif hasattr(team, 'conference'):
                division_name = f"{team.conference} Conference"
            else:
                division_name = "Eastern Conference" if hash(team.team_name) % 2 == 0 else "Western Conference"
            
            if division_name not in divisions:
                divisions[division_name] = []
            
            # Calculate points
            points = team.wins * 2 + getattr(team, 'ties', 0) + getattr(team, 'ot_losses', 0)
            
            divisions[division_name].append({
                'name': team.team_name,
                'record': f"{team.wins}-{team.losses}-{getattr(team, 'ties', 0)}",
                'points': points,
                'wins': team.wins,
                'losses': team.losses,
                'ties': getattr(team, 'ties', 0),
                'games_played': team.wins + team.losses + getattr(team, 'ties', 0)
            })
        
        # Sort by points
        for division in divisions:
            divisions[division].sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        
        return divisions
    
    def get_fallback_standings(self):
        """Fallback standings data if real data isn't available"""
        # Try to get some real teams first
        teams = self.get_fallback_teams()
        
        eastern_teams = []
        western_teams = []
        
        for i, team in enumerate(teams):
            team_data = {
                'name': team.team_name,
                'record': f"{team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}",
                'points': team.wins * 2 + getattr(team, 'ot_losses', 0),
                'wins': team.wins,
                'losses': team.losses,
                'ties': getattr(team, 'ot_losses', 0),
                'games_played': team.wins + team.losses + getattr(team, 'ot_losses', 0)
            }
            
            # Alternate between conferences
            if i % 2 == 0:
                eastern_teams.append(team_data)
            else:
                western_teams.append(team_data)
        
        return {
            "Eastern Conference": eastern_teams[:4],
            "Western Conference": western_teams[:4]
        }
    
    def get_team_stats_columns(self, category):
        """Get column definitions for team stats based on category"""
        base_columns = {
            'team': ('Team Name', 220),
            'gp': ('Games', 60),
        }
        
        if category == "Overall":
            return {**base_columns, 
                   'w': ('Wins', 55), 'l': ('Losses', 65), 't': ('OTL', 50), 'pts': ('Points', 65),
                   'gf': ('Goals For', 80), 'ga': ('Goals Against', 100), 'diff': ('Goal Diff', 80)}
        elif category == "Offense":
            return {**base_columns,
                   'gf': ('Goals For', 80), 'gpg': ('Goals/Game', 85), 'shots': ('Shots/Game', 90), 'pp': ('PP %', 65)}
        elif category == "Defense":
            return {**base_columns,
                   'ga': ('Goals Against', 100), 'gaa': ('Goals Against Avg', 120), 'shots_against': ('Shots Against', 100), 'pk': ('PK %', 65)}
        elif category == "Special Teams":
            return {**base_columns,
                   'pp': ('PowerPlay %', 90), 'pk': ('Penalty Kill %', 110), 'ppg': ('PP Goals', 80), 'shg': ('SH Goals', 80)}
        else:  # Goaltending
            return {**base_columns,
                   'gaa': ('Goals Against Avg', 120), 'sv_pct': ('Save %', 75), 'so': ('Shutouts', 75), 'wins': ('Wins', 55)}
    
    def get_player_leaders_columns(self, category):
        """Get column definitions for player leaders based on category"""
        if category == "scoring":
            return {
                'rank': ('#', 45),
                'name': ('Player Name', 180),
                'team': ('Team', 70),
                'pos': ('Pos', 55),
                'gp': ('GP', 45),
                'g': ('Goals', 55),
                'a': ('Assists', 65),
                'pts': ('Points', 65)
            }
        elif category == "goaltending":
            return {
                'rank': ('#', 45),
                'name': ('Goaltender', 180),
                'team': ('Team', 70),
                'gp': ('Starts', 60),
                'w': ('Wins', 50),
                'l': ('Losses', 60),
                'gaa': ('GAA', 65),
                'sv_pct': ('Save %', 70)
            }
        else:  # rookies
            return {
                'rank': ('#', 45),
                'name': ('Rookie Name', 180),
                'team': ('Team', 70),
                'pos': ('Pos', 55),
                'gp': ('GP', 45),
                'g': ('Goals', 55),
                'a': ('Assists', 65),
                'pts': ('Points', 65)
            }
    
    def populate_team_stats_data(self, tree, category):
        """Populate team stats with real game data"""
        try:
            # Get teams from game manager - properly access league object
            league = getattr(self.parent.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                teams = league.teams
            else:
                teams = []
                
            if not teams:
                # Fallback to sample data if no teams available
                self._populate_sample_team_stats(tree)
                return
            
            # Extract real team statistics
            team_stats = []
            for team in teams:
                try:
                    # Extract team statistics
                    games_played = getattr(team, 'games_played', 0)
                    wins = getattr(team, 'wins', 0)
                    losses = getattr(team, 'losses', 0) 
                    overtime_losses = getattr(team, 'overtime_losses', 0)
                    points = wins * 2 + overtime_losses
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    goal_diff = f"+{goals_for - goals_against}" if goals_for > goals_against else str(goals_for - goals_against)
                    
                    team_name = getattr(team, 'name', getattr(team, 'team_name', 'Unknown Team'))
                    team_stats.append((team_name, games_played, wins, losses, overtime_losses, points, goals_for, goals_against, goal_diff))
                    
                except Exception as e:
                    print(f"Error processing team {getattr(team, 'name', getattr(team, 'team_name', 'Unknown'))}: {e}")
                    continue
            
            # Sort by points (descending)
            team_stats.sort(key=lambda x: x[5], reverse=True)
            
            # Populate tree with real data
            for team_data in team_stats:
                tree.insert('', 'end', values=team_data)
                
        except Exception as e:
            print(f"Error populating team stats: {e}")
            # Fallback to sample data
            self._populate_sample_team_stats(tree)
    
    def _populate_sample_team_stats(self, tree):
        """Fallback method using real teams with calculated stats"""
        try:
            # Try to get some real teams first
            sample_teams = []
            if hasattr(self.parent, 'league') and self.parent.league.teams:
                real_teams = self.parent.league.teams[:8]  # Take first 8 teams
                
                for team in real_teams:
                    # Use real team data if available, fallback to 0 for missing stats
                    games_played = team.games_played
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    goal_diff = goals_for - goals_against
                    
                    team_data = (
                        team.team_name,
                        games_played,
                        team.wins,
                        team.losses,
                        getattr(team, 'ot_losses', 0),
                        team.points,
                        goals_for,
                        goals_against,
                        f"+{goal_diff}" if goal_diff >= 0 else str(goal_diff)
                    )
                    sample_teams.append(team_data)
            
            # If no real teams available, create minimal fallback display
            if not sample_teams:
                sample_teams = [
                    ("Loading teams...", 0, 0, 0, 0, 0, 0, 0, "0"),
                    ("Season starting...", 0, 0, 0, 0, 0, 0, 0, "0"),
                ]
                
        except Exception as e:
            print(f"Error creating team stats fallback: {e}")
            sample_teams = [
                ("Data loading...", 0, 0, 0, 0, 0, 0, 0, "0"),
            ]
        
        for team_data in sample_teams:
            tree.insert('', 'end', values=team_data)
    
    def populate_player_leaders_data(self, tree, category):
        """Populate player leaders with real game data"""
        # Get all players from all teams
        all_players = []
        
        try:
            # Get teams from game manager
            teams = []
            if hasattr(self.parent.game_manager, 'league'):
                if hasattr(self.parent.game_manager.league, 'teams'):
                    teams = self.parent.game_manager.league.teams
                elif hasattr(self.parent.game_manager.league, 'leagues'):
                    for league in self.parent.game_manager.league.leagues:
                        if hasattr(league, 'name') and "National Hockey League" in league.name:
                            teams = league.teams
                            break
            
            # Collect all players
            for team in teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        all_players.append({
                            'player': player,
                            'team_name': team.team_name
                        })
        
        except Exception as e:
            print(f"Error getting player data: {e}")
            # Fall back to real data with enhanced search
            self._populate_real_player_data(tree, category)
            return
        
        if not all_players:
            # Fall back to real data if no players found
            self._populate_real_player_data(tree, category)
            return
        
        # Sort and display based on category
        if category == "scoring":
            # Sort by points (goals + assists) from real player stats
            all_players.sort(key=lambda p: (getattr(p['player'], 'stats', None) and 
                                          (getattr(p['player'].stats, 'goals', 0) + getattr(p['player'].stats, 'assists', 0))) or 0, 
                           reverse=True)
            
            for i, player_data in enumerate(all_players[:20], 1):  # Top 20
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                
                # Get real stats if available
                stats = getattr(player, 'stats', None)
                if stats:
                    goals = getattr(stats, 'goals', 0)
                    assists = getattr(stats, 'assists', 0)
                    points = goals + assists
                    games_played = getattr(stats, 'games_played', 0)
                else:
                    # Generate realistic stats based on player attributes if no real stats
                    skill_rating = (getattr(player, 'shooting', 10) + 
                                  getattr(player, 'passing', 10) + 
                                  getattr(player, 'offensive_awareness', 10)) / 3
                    games_played = 0  # Start at 0 for new season
                    goals = max(0, int((skill_rating - 8) * games_played / 20))
                    assists = max(0, int((skill_rating - 7) * games_played / 18))
                    points = goals + assists
                
                # Show all players, including those with 0 stats at season start
                position_str = str(getattr(player, 'primary_position', 'C'))
                if '.' in position_str:
                    position_str = position_str.split('.')[-1]
                
                tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', f"{getattr(player, 'first_name', 'Unknown')} {getattr(player, 'last_name', 'Player')}"),
                    team_abbr,
                    position_str,
                    games_played,
                    goals,
                    assists,
                    points
                ))
                    
        elif category == "goaltending":
            # Filter for goalies and sort by wins
            goalies = [p for p in all_players if str(getattr(p['player'], 'primary_position', '')).endswith('GOALIE')]
            goalies.sort(key=lambda p: (getattr(p['player'], 'stats', None) and 
                                      getattr(p['player'].stats, 'wins', 0)) or 
                                     getattr(p['player'], 'goaltending', 0), reverse=True)
            
            for i, player_data in enumerate(goalies[:15], 1):  # Top 15 goalies
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                
                # Get real stats if available
                stats = getattr(player, 'stats', None)
                if stats:
                    games_played = getattr(stats, 'games_played', 0)
                    wins = getattr(stats, 'wins', 0)
                    losses = getattr(stats, 'losses', 0)
                    gaa = getattr(stats, 'goals_against_avg', 2.50)
                    save_pct = f".{getattr(stats, 'save_percentage', 915):03d}"
                else:
                    # Show 0 stats for goalies at season start
                    games_played = 0
                    wins = 0
                    losses = 0
                    gaa = 0.00
                    save_pct = ".000"
                
                # Show all goalies, including those with 0 games at season start
                tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', f"{getattr(player, 'first_name', 'Unknown')} {getattr(player, 'last_name', 'Player')}"),
                    team_abbr,
                    games_played,
                    wins,
                    losses,
                    gaa,
                    save_pct
                ))
                goals_against = getattr(player, 'goals_against', 0)
                saves = getattr(player, 'saves', 0)
                shots_against = saves + goals_against
                
                gaa = (goals_against / max(1, games_played)) * 82 if games_played > 0 else 0.0  # Normalized to 82-game season
                save_pct = (saves / max(1, shots_against)) if shots_against > 0 else 0.0
                
                # Show all goalies, including those with 0 games at season start
                tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', 'Unknown'),
                    team_abbr,
                    games_played,
                    wins,
                    losses,
                    f"{gaa:.2f}",
                    f"{save_pct:.3f}"
                ))
                    
        else:  # rookies
            # Filter for young players (age < 24) and sort by points
            rookies = [p for p in all_players if getattr(p['player'], 'age', 30) < 24]
            rookies.sort(key=lambda p: getattr(p['player'], 'goals', 0) + getattr(p['player'], 'assists', 0), reverse=True)
            
            for i, player_data in enumerate(rookies[:15], 1):  # Top 15 rookies
                player = player_data['player']
                team_abbr = self._get_team_abbreviation(player_data['team_name'])
                goals = getattr(player, 'goals', 0)
                assists = getattr(player, 'assists', 0)
                points = goals + assists
                games_played = getattr(player, 'games_played', 0)
                
                # Show all rookies, including those with 0 stats at season start
                tree.insert('', 'end', values=(
                    i,
                    getattr(player, 'full_name', 'Unknown'),
                    team_abbr,
                    getattr(player, 'primary_position', 'C'),
                    games_played,
                    goals,
                    assists,
                    points
                ))
    
    def _get_team_abbreviation(self, team_name):
        """Get team abbreviation from full name"""
        abbreviations = {
            'Boston Bruins': 'BOS',
            'Buffalo Sabres': 'BUF',
            'Detroit Red Wings': 'DET',
            'Montreal Canadiens': 'MTL',
            'Toronto Maple Leafs': 'TOR',
            'Tampa Bay Lightning': 'TBL',
            'Pittsburgh Penguins': 'PIT',
            'Chicago Blackhawks': 'CHI',
            'Colorado Avalanche': 'COL',
            'Edmonton Oilers': 'EDM',
            'Calgary Flames': 'CGY',
            'Vancouver Canucks': 'VAN',
            'Vegas Golden Knights': 'VGK',
        }
        
        return abbreviations.get(team_name, team_name[:3].upper())
    
    def _populate_real_player_data(self, tree, category):
        """Enhanced method that uses real player data and calculates realistic stats"""
        try:
            # Try to get real players from multiple sources
            all_players = []
            
            # Primary source: game manager league
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
                league = self.parent.game_manager.league
                if hasattr(league, 'teams'):
                    for team in league.teams:
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                            if hasattr(team, 'roster'):
                                all_players.extend(team.roster)
            
            # Secondary source: direct league access
            if not all_players and hasattr(self.parent, 'league'):
                for team in getattr(self.parent.league, 'teams', []):
                    if hasattr(team, 'roster'):
                        all_players.extend(team.roster)
            
            # Tertiary source: user team league
            if not all_players and hasattr(self.parent, 'user_team'):
                if hasattr(self.parent.user_team, 'league'):
                    for team in getattr(self.parent.user_team.league, 'teams', []):
                        if hasattr(team, 'roster'):
                            all_players.extend(team.roster)
            
            if all_players:
                # Sort players by their current stats or calculate from attributes
                if category == "scoring":
                    sorted_players = sorted(all_players, 
                                          key=lambda p: getattr(p, 'points', getattr(p, 'goals', 0) + getattr(p, 'assists', 0)), 
                                          reverse=True)[:20]
                elif category == "goalies":
                    goalies = [p for p in all_players if 'GOALIE' in str(p.primary_position).upper()]
                    sorted_players = sorted(goalies, 
                                          key=lambda p: getattr(p, 'save_percentage', 0.900), 
                                          reverse=True)[:10]
                else:  # breakout or other
                    young_players = [p for p in all_players if p.age <= 25]
                    sorted_players = sorted(young_players, 
                                          key=lambda p: p.overall_rating(), 
                                          reverse=True)[:15]
                
                # Populate with real player data
                for i, player in enumerate(sorted_players, 1):
                    try:
                        if category == "scoring":
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                str(player.primary_position),
                                getattr(player, 'goals', 0),
                                getattr(player, 'assists', 0),
                                getattr(player, 'points', getattr(player, 'goals', 0) + getattr(player, 'assists', 0)),
                                getattr(player, 'games_played', 0)
                            )
                        elif category == "goalies":
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                getattr(player, 'wins', 0),
                                getattr(player, 'losses', 0),
                                getattr(player, 'saves', 0),
                                f"{getattr(player, 'goals_against_average', 2.50):.2f}",
                                f"{getattr(player, 'save_percentage', 0.900):.3f}"
                            )
                        else:  # breakout
                            values = (
                                str(i),
                                player.full_name,
                                getattr(player, 'team_name', 'NHL'),
                                str(player.primary_position),
                                getattr(player, 'goals', 0),
                                getattr(player, 'assists', 0),
                                getattr(player, 'points', getattr(player, 'goals', 0) + getattr(player, 'assists', 0)),
                                player.age
                            )
                        
                        tree.insert('', 'end', values=values)
                        
                    except Exception as e:
                        print(f"Error adding player {player.full_name}: {e}")
                        continue
                        
                return  # Successfully populated with real data
                
        except Exception as e:
            print(f"Error getting real player data: {e}")
        
        # If all else fails, use calculated data from available teams
        self._populate_calculated_player_data(tree, category)
    
    def _populate_calculated_player_data(self, tree, category):
        """Generate calculated player data from available team information - starts at 0 for new season"""
        try:
            # Get teams and show placeholder data with 0 stats for new season
            teams = self.get_fallback_teams()[:8]
            rank = 1
            
            for team in teams:
                # Generate 2-3 players per team with 0 stats for season start
                for i in range(3):  # 3 players per team
                    if rank > 20:  # Limit to top 20
                        break
                        
                    player_name = f"{team.team_name} Player {i+1}"
                    
                    if category == "scoring":
                        # Start season with 0 stats
                        goals = 0
                        assists = 0
                        points = 0
                        games = 0
                        
                        values = (str(rank), player_name, team.team_name, "C", goals, assists, points, games)
                    elif category == "goalies":
                        if i == 0:  # Only one goalie per team
                            wins = 0
                            losses = 0
                            saves = 0
                            gaa = 0.00
                            sv_pct = 0.000
                            
                            values = (str(rank), player_name, team.team_name, wins, losses, saves, f"{gaa:.2f}", f"{sv_pct:.3f}")
                        else:
                            continue
                    else:  # breakout
                        goals = 0
                        assists = 0
                        points = 0
                        age = 20 + i
                        
                        values = (str(rank), player_name, team.team_name, "C", goals, assists, points, age)
                    
                    tree.insert('', 'end', values=values)
                    rank += 1
                    
        except Exception as e:
            print(f"Error generating calculated player data: {e}")
            # Final fallback - minimal data display
            tree.insert('', 'end', values=("--", "No data available", "---", "---", 0, 0, 0, 0))
                                # Base games on player skill and team performance
    def update_standings_view(self, event=None):
        """Update standings view when selection changes"""
        self.populate_standings()
    
    def update_team_stats_view(self, event=None):
        """Update team stats view when category changes"""
        self.populate_team_stats()
    
    def refresh_all_data(self):
        """Refresh all data in the window"""
        try:
            # Update current status
            self.status_label.config(text="Refreshing data...")
            self.update()
            
            # Refresh based on current tab
            current_tab = self.notebook.index(self.notebook.select())
            if current_tab == 0:  # Standings
                self.populate_enhanced_standings()
            elif current_tab == 1:  # Team Stats
                self.populate_advanced_team_stats()
            elif current_tab == 2:  # Player Leaders
                self.update_player_leaders()
            elif current_tab == 3:  # Analytics
                self.refresh_analytics_dashboard()
            elif current_tab == 4:  # Trends
                self.update_trends_analysis()
            elif current_tab == 5:  # Divisions
                self.update_division_analysis()
                
            # Update timestamp
            current_time = datetime.now().strftime("%H:%M:%S")
            self.status_label.config(text=f"Last updated: {current_time}")
            
        except Exception as e:
            self.status_label.config(text=f"Error refreshing data: {str(e)}")
    
    def export_data(self):
        """Export current data to file"""
        try:
            from datetime import datetime
            import csv
            import os
            
            # Get current tab and data
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            
            # Define export filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hockey_stats_{current_tab.lower().replace(' ', '_')}_{timestamp}.csv"
            
            # Get the appropriate data based on current tab
            if current_tab == "League Leaders":
                data = self.get_current_leaders_data()
                headers = ["Rank", "Player", "Team", "Position", "Goals", "Assists", "Points", "Games"]
            elif current_tab == "Team Standings":
                data = self.get_current_standings_data()
                headers = ["Rank", "Team", "GP", "W", "L", "OT", "Points", "GF", "GA", "Diff"]
            elif current_tab == "Advanced Stats":
                data = self.get_current_advanced_data()
                headers = ["Rank", "Player", "Team", "Position", "Corsi", "Fenwick", "PDO", "TOI/G"]
            else:
                # General export for other tabs
                data = self.get_current_view_data()
                headers = ["Data exported from", current_tab]
            
            if data:
                # Create exports directory if it doesn't exist
                exports_dir = "exports"
                if not os.path.exists(exports_dir):
                    os.makedirs(exports_dir)
                
                filepath = os.path.join(exports_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerows(data)
                
                tk.messagebox.showinfo("Export Successful", 
                                     f"Data exported to:\n{filepath}\n\n{len(data)} records exported.")
            else:
                tk.messagebox.showwarning("Export Warning", "No data available to export.")
                
        except Exception as e:
            print(f"Error exporting data: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export data:\n{str(e)}")
    
    def get_current_leaders_data(self):
        """Get current leaders data for export"""
        try:
            # Get the data from the current page
            current_tree = getattr(self, 'current_leaders_tree', None)
            if current_tree:
                data = []
                for child in current_tree.get_children():
                    values = current_tree.item(child)['values']
                    data.append(values)
                return data
        except:
            pass
        return []
    
    def get_current_standings_data(self):
        """Get current standings data for export"""
        try:
            # Export team standings
            data = []
            rank = 1
            for team in sorted(self.parent.league.teams, key=lambda t: t.points, reverse=True):
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    data.append([
                        rank,
                        team.team_name,
                        team.games_played,
                        team.wins,
                        team.losses,
                        team.overtimes,
                        team.points,
                        team.goals_for,
                        team.goals_against,
                        team.goal_differential
                    ])
                    rank += 1
            return data
        except:
            return []
    
    def get_current_advanced_data(self):
        """Get current advanced stats data for export"""
        try:
            # Export advanced stats data
            data = []
            rank = 1
            all_players = []
            
            for team in self.parent.league.teams:
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    for player in team.roster:
                        all_players.append(player)
            
            # Sort by some advanced metric (using plus_minus as example)
            sorted_players = sorted(all_players, 
                                  key=lambda p: getattr(p, 'plus_minus', 0), reverse=True)[:50]
            
            for player in sorted_players:
                corsi = getattr(player, 'corsi_for_percent', 50.0)
                fenwick = getattr(player, 'fenwick_for_percent', 50.0)
                pdo = getattr(player, 'pdo', 100.0)
                toi = getattr(player, 'time_on_ice_per_game', 15.0)
                
                data.append([
                    rank,
                    player.full_name,
                    player.team_name,
                    player.primary_position.value if hasattr(player.primary_position, 'value') else str(player.primary_position),
                    f"{corsi:.1f}%",
                    f"{fenwick:.1f}%",
                    f"{pdo:.1f}",
                    f"{toi:.1f}"
                ])
                rank += 1
            
            return data
        except:
            return []
    
    def get_current_view_data(self):
        """Get current view data for export"""
        # Fallback method for general data export
        return [["Export completed", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]
    
    def on_tab_changed(self, event=None):
        """Handle tab change events"""
        current_tab = self.notebook.index(self.notebook.select())
        self.selected_tab = current_tab
        
        # Load data for the selected tab if not already loaded
        self.load_tab_data(current_tab)
    
    def on_filter_change(self, event=None):
        """Handle global filter changes"""
        # Update filters dictionary
        self.filters['time_period'] = self.period_var.get()
        
        # Refresh current tab data
        self.refresh_all_data()
    
    def load_tab_data(self, tab_index):
        """Load data for specific tab"""
        if tab_index == 0:  # Standings
            self.populate_enhanced_standings()
        elif tab_index == 1:  # Team Stats
            self.populate_advanced_team_stats()
        elif tab_index == 2:  # Player Leaders
            self.update_player_leaders()
        elif tab_index == 3:  # Analytics
            self.refresh_analytics_dashboard()
        elif tab_index == 4:  # Trends
            self.populate_trends_analysis()
        elif tab_index == 5:  # Divisions
            self.populate_division_analysis()
    
    # Enhanced populate methods
    def populate_enhanced_standings(self):
        """Populate enhanced standings with advanced metrics"""
        # Clear existing content
        for widget in self.standings_scrollable.winfo_children():
            widget.destroy()
        
        view_type = self.standings_view.get()
        
        # Create enhanced standings table
        self.create_enhanced_standings_table(self.standings_scrollable, view_type)
    
    def create_enhanced_standings_table(self, parent, view_type):
        """Create enhanced standings table with advanced metrics"""
        # Column definitions based on view type and advanced metrics setting
        if self.show_advanced.get():
            columns = {
                'rank': ('Rank', 50),
                'team': ('Team', 150),
                'gp': ('GP', 40),
                'w': ('W', 35),
                'l': ('L', 35),
                'otl': ('OTL', 40),
                'pts': ('PTS', 45),
                'pt_pct': ('PT%', 50),
                'gf': ('GF', 40),
                'ga': ('GA', 40),
                'diff': ('+/-', 45),
                'home': ('Home', 60),
                'road': ('Road', 60),
                'l10': ('L10', 50),
                'streak': ('Streak', 60),
                'playoff': ('Playoff', 70)
            }
        else:
            columns = {
                'rank': ('Rank', 50),
                'team': ('Team', 150),
                'gp': ('GP', 40),
                'w': ('W', 35),
                'l': ('L', 35),
                'otl': ('OTL', 40),
                'pts': ('PTS', 45),
                'pt_pct': ('PT%', 50),
                'diff': ('+/-', 45),
                'l10': ('L10', 50)
            }
        
        # Create treeview
        tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                           show='headings', height=25)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='center')
            tree.column(col_id, width=width, anchor='center')
        
        # Use real data with fallback
        self.add_enhanced_standings_data(tree, view_type, self.show_advanced.get())
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def add_enhanced_standings_data(self, tree, view_type, show_advanced):
        """Add enhanced standings data with real team information"""
        # Get teams from parent application
        teams = []
        if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'league'):
            # Check if league has teams directly or nested leagues
            if hasattr(self.parent.game_manager.league, 'teams'):
                teams = self.parent.game_manager.league.teams
            elif hasattr(self.parent.game_manager.league, 'leagues'):
                # Look for NHL in nested leagues
                for league in self.parent.game_manager.league.leagues:
                    if hasattr(league, 'name') and "National Hockey League" in league.name:
                        teams = league.teams
                        break
            
        # If no teams found, try alternative data sources
        if not teams:
            teams = self.get_fallback_teams()
        
        # Sort teams by points
        sorted_teams = sorted(teams, key=lambda t: (t.wins * 2 + getattr(t, 'ot_losses', 0)), reverse=True)
        
        for rank, team in enumerate(sorted_teams[:30], 1):  # Show top 30 teams
            try:
                gp = team.wins + team.losses + getattr(team, 'ot_losses', 0)
                points = team.wins * 2 + getattr(team, 'ot_losses', 0)
                pt_pct = (points / max(1, gp) * 100) if gp > 0 else 0.0
                
                if show_advanced:
                    # Get real team statistics instead of random data
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0) 
                    goal_diff = goals_for - goals_against
                    
                    # Calculate home/away records from actual data if available
                    home_record = f"{getattr(team, 'home_wins', 0)}-{getattr(team, 'home_losses', 0)}-{getattr(team, 'home_ot_losses', 0)}"
                    road_record = f"{getattr(team, 'away_wins', 0)}-{getattr(team, 'away_losses', 0)}-{getattr(team, 'away_ot_losses', 0)}"
                    
                    # Last 10 games record (would need game history - using simplified calculation)
                    recent_games = min(10, gp)
                    if recent_games > 0:
                        # Estimate recent performance based on overall record
                        recent_wins = min(recent_games, max(1, int(team.wins * recent_games / gp))) if gp > 0 else 0
                        recent_losses = recent_games - recent_wins
                        l10_record = f"{recent_wins}-{recent_losses}-0"
                    else:
                        l10_record = "0-0-0"
                    
                    # Calculate streak (simplified - would need game history)
                    if team.wins > team.losses:
                        streak = f"W{min(3, team.wins)}"
                    elif team.losses > team.wins:
                        streak = f"L{min(3, team.losses)}"
                    else:
                        streak = "T1"
                    
                    values = (
                        rank,
                        team.team_name,
                        gp,  # GP
                        team.wins,
                        team.losses,
                        getattr(team, 'ot_losses', 0),
                        points,  # Points
                        f"{pt_pct:.1f}%",  # PT%
                        goals_for,  # GF (real data)
                        goals_against,  # GA (real data)
                        goal_diff,  # +/- (calculated)
                        home_record,  # Home record (real data)
                        road_record,  # Road record (real data)
                        l10_record,  # L10 (calculated)
                        streak,  # Streak (calculated)
                        "In" if rank <= 16 else "Out"  # Playoff position
                    )
                else:
                    goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
                    # Calculate last 10 for basic view
                    recent_games = min(10, gp)
                    if recent_games > 0:
                        recent_wins = min(recent_games, max(1, int(team.wins * recent_games / gp))) if gp > 0 else 0
                        recent_losses = recent_games - recent_wins
                        l10_record = f"{recent_wins}-{recent_losses}-0"
                    else:
                        l10_record = "0-0-0"
                    
                    values = (
                        rank,
                        team.team_name,
                        gp,  # GP
                        team.wins,
                        team.losses,
                        getattr(team, 'ot_losses', 0),
                        points,  # Points
                        f"{pt_pct:.1f}%",  # PT%
                        goal_diff,  # +/- (calculated from real data)
                        l10_record  # L10 (calculated)
                    )
                
                # Color coding for playoff positions
                if rank <= 8:
                    tree.insert('', 'end', values=values, tags=('playoff',))
                elif rank <= 16:
                    tree.insert('', 'end', values=values, tags=('wildcard',))
                else:
                    tree.insert('', 'end', values=values)
                    
            except Exception as e:
                print(f"Error processing team {team.team_name}: {e}")
                continue
        
        # Configure tag colors
        tree.tag_configure('playoff', background='#166534', foreground='#FFFFFF')  # Dark green with white text
        tree.tag_configure('wildcard', background='#CA8A04', foreground='#FFFFFF')  # Dark yellow with white text
    
    def get_fallback_teams(self):
        """Get teams from alternative data sources if main source fails"""
        try:
            # Try direct access to parent league
            if hasattr(self.parent, 'league') and hasattr(self.parent.league, 'teams'):
                teams = [team for team in self.parent.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
                if teams:
                    return teams
            
            # Try accessing user team's league
            if hasattr(self.parent, 'user_team') and hasattr(self.parent.user_team, 'league'):
                teams = getattr(self.parent.user_team.league, 'teams', [])
                if teams:
                    return teams
            
            # Try game manager league access
            league = getattr(self.parent.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                teams = league.teams
                if teams:
                    return teams
                    
        except Exception as e:
            print(f"Error getting fallback teams: {e}")
        
        # Final fallback - create minimal realistic teams from available data
        from game_classes import Team
        fallback_teams = []
        team_names = ["Boston Bruins", "Toronto Maple Leafs", "Tampa Bay Lightning", "Florida Panthers",
                     "Buffalo Sabres", "Ottawa Senators", "Montreal Canadiens", "Detroit Red Wings"]
        
        for i, name in enumerate(team_names):
            team = Team(name)
            # Set all stats to 0 for season start
            team.wins = 0
            team.losses = 0
            team.goals_for = 0
            team.goals_against = 0
            team.games_played = 0
            fallback_teams.append(team)
        
        return fallback_teams
    
    def populate_advanced_team_stats(self):
        """Populate advanced team statistics"""
        # Clear existing content
        for widget in self.team_stats_container.winfo_children():
            widget.destroy()
        
        category = self.stats_category.get()
        mode = self.stats_mode.get()
        
        self.create_advanced_stats_table(self.team_stats_container, category, mode)
    
    def create_advanced_stats_table(self, parent, category, mode):
        """Create advanced statistics table"""
        columns = self.get_advanced_stats_columns(category)
        
        # Create treeview
        tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                           show='headings', height=20)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='center')
            tree.column(col_id, width=width, anchor='center')
        
        # Use real advanced statistics data
        self.add_advanced_stats_data(tree, category, mode)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def get_advanced_stats_columns(self, category):
        """Get column definitions for advanced stats"""
        if category == "Overall Performance":
            return {
                'team': ('Team', 150),
                'pts_pct': ('Points %', 80),
                'expected_pts': ('xPTS', 60),
                'pdo': ('PDO', 60),
                'corsi_for': ('CF%', 60),
                'fenwick_for': ('FF%', 60),
                'shot_attempt_diff': ('SA Diff', 80),
                'quality_starts': ('QS%', 60)
            }
        elif category == "Advanced Analytics":
            return {
                'team': ('Team', 150),
                'expected_goals_for': ('xGF', 60),
                'expected_goals_against': ('xGA', 60),
                'shooting_pct': ('SH%', 60),
                'save_pct': ('SV%', 60),
                'pdo': ('PDO', 60),
                'zone_start_pct': ('ZS%', 60),
                'high_danger_for': ('HD CF%', 80)
            }
        else:
            return {
                'team': ('Team', 150),
                'stat1': ('Stat 1', 80),
                'stat2': ('Stat 2', 80),
                'stat3': ('Stat 3', 80),
                'stat4': ('Stat 4', 80)
            }
    
    def add_advanced_stats_data(self, tree, category, mode):
        """Add advanced statistics data"""
        try:
            # Get real teams
            league = getattr(self.parent.game_manager, 'league', None)
            if league and hasattr(league, 'teams'):
                teams = league.teams
            else:
                teams = []
                
            if not teams:
                teams = self.get_fallback_teams()
            
            # Extract and calculate advanced stats from real data
            for team in teams:
                team_name = getattr(team, 'name', getattr(team, 'team_name', 'Unknown Team'))
                
                if category == "Overall Performance":
                    # Calculate real advanced stats where possible
                    games_played = getattr(team, 'games_played', 0)
                    wins = getattr(team, 'wins', 0)
                    ot_losses = getattr(team, 'overtime_losses', getattr(team, 'ot_losses', 0))
                    points = wins * 2 + ot_losses
                    points_pct = points / (games_played * 2) if games_played > 0 else 0.0
                    
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    
                    # Calculate advanced metrics with real data where available
                    expected_points = int(points_pct * 82 * 2)  # Projected over full season
                    pdo = 100.0  # Default PDO (normally shooting% + save%)
                    
                    # Use analytics engine if available
                    if hasattr(self, 'analytics_engine') and self.analytics_engine:
                        # Look up team stats from our analytics engine
                        team_analytics = self.analytics_engine.team_stats.get(team_name)
                        if team_analytics:
                            # Use possession_percentage if available, otherwise default
                            possession_pct = getattr(team_analytics, 'possession_percentage', 50.0)
                            corsi_for_pct = f"{possession_pct:.1f}%"
                            fenwick_for_pct = corsi_for_pct  # Simplified
                        else:
                            corsi_for_pct = "50.0%"
                            fenwick_for_pct = "50.0%"
                    else:
                        corsi_for_pct = "50.0%"
                        fenwick_for_pct = "50.0%"
                    
                    shot_diff = goals_for - goals_against  # Simplified shot differential
                    quality_start_pct = f"{min(65.0, 45.0 + (points_pct * 20)):.1f}%"
                    
                    values = (
                        team_name,
                        f"{points_pct:.3f}",
                        expected_points,
                        f"{pdo:.1f}",
                        corsi_for_pct,
                        fenwick_for_pct,
                        shot_diff,
                        quality_start_pct
                    )
                elif category == "Advanced Analytics":
                    # Calculate expected goals and advanced metrics
                    goals_for = getattr(team, 'goals_for', 0)
                    goals_against = getattr(team, 'goals_against', 0)
                    games_played = getattr(team, 'games_played', 0)
                    
                    xgf = goals_for / max(1, games_played)  # Expected goals for per game
                    xga = goals_against / max(1, games_played)  # Expected goals against per game
                    
                    # Estimate shooting percentage (simplified)
                    shooting_pct = f"{min(15.0, max(8.0, (goals_for / max(1, games_played * 30)) * 100)):.1f}%"
                    save_pct = f"{max(0.885, min(0.925, 1 - (goals_against / max(1, games_played * 30)))):.3f}"
                    
                    pdo = 100.0  # Default PDO
                    zone_start_pct = "50.0%"  # Default zone start percentage
                    hd_corsi_pct = "50.0%"   # Default high danger Corsi
                    
                    values = (
                        team_name,
                        f"{xgf:.2f}",
                        f"{xga:.2f}",
                        shooting_pct,
                        save_pct,
                        f"{pdo:.1f}",
                        zone_start_pct,
                        hd_corsi_pct
                    )
                else:
                    values = (team_name, "0.0", "0.0", "0.0", "0.0")
                
                tree.insert('', 'end', values=values)
                
        except Exception as e:
            print(f"Error adding advanced stats data: {e}")
            # Fallback to basic calculated data
            self._add_calculated_advanced_stats(tree, category)
    
    def _add_calculated_advanced_stats(self, tree, category):
        """Fallback method for calculated advanced stats using available team data"""
        # Get real teams and calculate stats from their basic data
        teams = []
        try:
            if hasattr(self.parent, 'league') and hasattr(self.parent.league, 'teams'):
                teams = [team for team in self.parent.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"][:8]
        except:
            pass
        
        if not teams:
            teams = self.get_fallback_teams()[:8]
        
        for team in teams:
            try:
                # Calculate advanced metrics from basic team stats
                gf = getattr(team, 'goals_for', 0)
                ga = getattr(team, 'goals_against', 0) 
                gp = getattr(team, 'games_played', 1)
                
                if category == "Expected Goals":
                    # Estimate xG based on goals and game performance
                    xgf = gf * 0.95  # Slightly lower than actual goals
                    xga = ga * 1.05  # Slightly higher than actual goals against
                    shooting_pct = f"{(gf / max(1, gp * 30)) * 100:.1f}%"  # Estimated shots
                    save_pct = f"{(1 - (ga / max(1, gp * 30))) * 100:.1f}%"  # Estimated saves
                    
                    values = (
                        team.team_name,
                        f"{xgf:.2f}",
                        f"{xga:.2f}",
                        shooting_pct,
                        save_pct,
                        f"{100.0:.1f}",  # PDO
                        "50.0%",  # Zone start %
                        "50.0%"   # HD Corsi %
                    )
                else:
                    # Basic fallback values
                    values = (team.team_name, "0.0", "0.0", "0.0", "0.0")
                
                tree.insert('', 'end', values=values)
                
            except Exception as e:
                print(f"Error calculating stats for {team.team_name}: {e}")
                continue
            if category == "Overall Performance":
                values = (team, "0.600", "98", "100.0", "52.0%", "51.5%", "25", "58.0%")
            elif category == "Advanced Analytics":
                values = (team, "3.20", "2.95", "10.5%", "0.910", "100.5", "52.0%", "51.0%")
            else:
                values = (team, "0.0", "0.0", "0.0", "0.0")
            
            tree.insert('', 'end', values=values)
    
    def create_enhanced_player_section(self, parent, category):
        """Create enhanced player leaders section with pagination"""
        # Initialize pagination data for this category if not exists
        if not hasattr(self, 'pagination_data'):
            self.pagination_data = {}
        
        if category not in self.pagination_data:
            self.pagination_data[category] = {
                'current_page': 1,
                'players_per_page': 50,  # Show more players by default
                'total_players': 0,
                'all_players': []
            }
        
        # Create main container
        main_container = ttk.Frame(parent)
        main_container.pack(fill="both", expand=True)
        
        # Create pagination controls at top
        pagination_frame = ttk.Frame(main_container)
        pagination_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        # Page info and controls
        self.create_pagination_controls(pagination_frame, category)
        
        # Create treeview container
        tree_container = ttk.Frame(main_container)
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        columns = self.get_enhanced_player_columns(category)
        
        # Create treeview with enhanced features
        tree = ttk.Treeview(tree_container, columns=list(columns.keys()), 
                           show='headings', height=20)
        
        # Configure columns
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='center')
            tree.column(col_id, width=width, anchor='center')
        
        # Store tree reference for pagination updates
        self.pagination_data[category]['tree'] = tree
        
        # Add keyboard bindings for pagination
        tree.bind('<Prior>', lambda e: self.go_to_page(category, self.pagination_data[category]['current_page'] - 1))  # Page Up
        tree.bind('<Next>', lambda e: self.go_to_page(category, self.pagination_data[category]['current_page'] + 1))   # Page Down
        tree.bind('<Home>', lambda e: self.go_to_page(category, 1))  # Home key
        tree.bind('<End>', lambda e: self.go_to_last_page(category))  # End key
        tree.focus_set()  # Allow tree to receive keyboard events
        
        # Load and display first page of data
        self.load_all_players_data(category)
        self.update_page_display(category)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_pagination_controls(self, parent, category):
        """Create pagination controls for player stats"""
        # Left side - page info
        info_frame = ttk.Frame(parent)
        info_frame.pack(side="left")
        
        page_label = ttk.Label(info_frame, text="", style='TLabel')
        page_label.pack(side="left", padx=(0, 20))
        
        # Store reference for updates
        self.pagination_data[category]['page_label'] = page_label
        
        # Center - navigation buttons
        nav_frame = ttk.Frame(parent)
        nav_frame.pack(side="left", expand=True)
        
        # First page button
        first_btn = ttk.Button(nav_frame, text="⏮ First", 
                              command=lambda: self.go_to_page(category, 1))
        first_btn.pack(side="left", padx=2)
        
        # Previous page button
        prev_btn = ttk.Button(nav_frame, text="◀ Previous", 
                             command=lambda: self.go_to_page(category, 
                             self.pagination_data[category]['current_page'] - 1))
        prev_btn.pack(side="left", padx=2)
        
        # Page number entry
        page_entry_frame = ttk.Frame(nav_frame)
        page_entry_frame.pack(side="left", padx=10)
        
        ttk.Label(page_entry_frame, text="Page:", style='TLabel').pack(side="left")
        page_entry = ttk.Entry(page_entry_frame, width=4, justify='center')
        page_entry.pack(side="left", padx=(5, 0))
        page_entry.bind('<Return>', lambda e: self.go_to_page_from_entry(category, page_entry))
        
        self.pagination_data[category]['page_entry'] = page_entry
        
        # Next page button
        next_btn = ttk.Button(nav_frame, text="Next ▶", 
                             command=lambda: self.go_to_page(category, 
                             self.pagination_data[category]['current_page'] + 1))
        next_btn.pack(side="left", padx=2)
        
        # Last page button
        last_btn = ttk.Button(nav_frame, text="Last ⏭", 
                             command=lambda: self.go_to_last_page(category))
        last_btn.pack(side="left", padx=2)
        
        # Store button references for enabling/disabling
        self.pagination_data[category]['buttons'] = {
            'first': first_btn,
            'prev': prev_btn,
            'next': next_btn,
            'last': last_btn
        }
        
        # Right side - players per page selector
        per_page_frame = ttk.Frame(parent)
        per_page_frame.pack(side="right")
        
        ttk.Label(per_page_frame, text="Per page:", style='TLabel').pack(side="left")
        per_page_var = tk.StringVar(value="50")  # Default to 50 players per page
        per_page_combo = ttk.Combobox(per_page_frame, textvariable=per_page_var,
                                     values=["10", "25", "50", "100", "All"], 
                                     width=5, state="readonly")
        per_page_combo.pack(side="left", padx=(5, 0))
        per_page_combo.bind('<<ComboboxSelected>>', 
                           lambda e: self.change_per_page(category, per_page_var.get()))
        
        self.pagination_data[category]['per_page_var'] = per_page_var
    
    def get_enhanced_player_columns(self, category):
        """Get enhanced column definitions for player stats"""
        if category == "scoring":
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'pos': ('Pos', 50),
                'gp': ('GP', 40),
                'goals': ('G', 40),
                'assists': ('A', 40),
                'points': ('PTS', 50),
                'ppg': ('PPG', 50),
                'plus_minus': ('+/-', 50),
                'pim': ('PIM', 45),
                'shots': ('SOG', 50)
            }
        elif category == "advanced":
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'pos': ('Pos', 50),
                'gp': ('GP', 40),
                'corsi_for': ('CF%', 60),
                'expected_goals': ('xG', 50),
                'shooting_pct': ('SH%', 50),
                'pdo': ('PDO', 60),
                'zone_starts': ('ZS%', 60)
            }
        elif category == "breakout":
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'age': ('Age', 40),
                'improvement': ('Improvement', 100),
                'current_pace': ('Current Pace', 90),
                'projection': ('Season Projection', 120)
            }
        else:  # goaltending
            return {
                'rank': ('Rank', 50),
                'player': ('Player', 150),
                'team': ('Team', 60),
                'gp': ('GP', 40),
                'w': ('W', 35),
                'l': ('L', 35),
                'gaa': ('GAA', 50),
                'sv_pct': ('SV%', 60),
                'so': ('SO', 40),
                'gsaa': ('GSAA', 60)
            }
    
    def add_enhanced_player_data(self, tree, category):
        """Add enhanced player data from real game data"""
        try:
            all_players = []
            
            # Collect all players from all teams
            for team in self.parent.league.teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        if category == "goaltending":
                            # Only include goalies for goaltending stats
                            if hasattr(player, 'primary_position') and 'G' in str(player.primary_position):
                                all_players.append((player, team))
                        else:
                            # Include all non-goalies for other categories
                            if not (hasattr(player, 'primary_position') and 'G' in str(player.primary_position)):
                                all_players.append((player, team))
            
            if category == "scoring":
                # Sort by points (goals + assists)
                def get_points(player_team):
                    player, team = player_team
                    goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                    assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                    return goals + assists
                
                sorted_players = sorted(all_players, key=get_points, reverse=True)[:20]  # Top 20
                
                for rank, (player, team) in enumerate(sorted_players, 1):
                    goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                    assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                    games = getattr(player.stats, 'games_played', 0) if hasattr(player, 'stats') else 0
                    points = goals + assists
                    ppg = round(points / max(games, 1), 2)
                    plus_minus = getattr(player.stats, 'plus_minus', 0) if hasattr(player, 'stats') else 0
                    pim = getattr(player.stats, 'pim', 0) if hasattr(player, 'stats') else 0
                    shots = getattr(player.stats, 'shots', 0) if hasattr(player, 'stats') else 0
                    
                    position = str(getattr(player, 'primary_position', 'F'))
                    if hasattr(player, 'primary_position') and hasattr(player.primary_position, 'value'):
                        position = player.primary_position.value
                    
                    player_data = (
                        rank, player.full_name, self._get_team_abbreviation(team.team_name), position,
                        games, goals, assists, points, ppg, plus_minus, pim, shots
                    )
                    tree.insert('', 'end', values=player_data)
                    
            elif category == "advanced":
                # Sort by a combination of advanced stats (use shooting percentage as primary)
                def get_advanced_score(player_team):
                    player, team = player_team
                    # Use shooting and overall rating as advanced metric
                    shooting = getattr(player, 'shooting', 10)
                    overall = getattr(player, 'overall_rating', lambda: 75)() if callable(getattr(player, 'overall_rating', None)) else 75
                    return shooting + (overall * 0.1)
                
                sorted_players = sorted(all_players, key=get_advanced_score, reverse=True)[:15]  # Top 15
                
                for rank, (player, team) in enumerate(sorted_players, 1):
                    games = getattr(player.stats, 'games_played', 0) if hasattr(player, 'stats') else 0
                    
                    # Calculate advanced stats from player attributes
                    corsi_for = f"{round(50 + getattr(player, 'offensive_awareness', 10) * 0.5, 1)}%"
                    expected_goals = round(getattr(player, 'shooting', 10) * 0.8, 1)
                    shooting_pct = f"{round(getattr(player, 'shooting_accuracy', 10) * 0.8, 1)}%"
                    pdo = round(100 + getattr(player, 'luck', 0) * 2, 1) if hasattr(player, 'luck') else 100.0
                    zone_starts = f"{round(50 + getattr(player, 'positioning', 10) * 0.3, 1)}%"
                    
                    position = str(getattr(player, 'primary_position', 'F'))
                    if hasattr(player, 'primary_position') and hasattr(player.primary_position, 'value'):
                        position = player.primary_position.value
                    
                    player_data = (
                        rank, player.full_name, self._get_team_abbreviation(team.team_name), position,
                        games, corsi_for, expected_goals, shooting_pct, pdo, zone_starts
                    )
                    tree.insert('', 'end', values=player_data)
                    
            elif category == "breakout":
                # Focus on younger players with high potential
                young_players = [(p, t) for p, t in all_players if getattr(p, 'age', 25) <= 23]
                
                def get_breakout_potential(player_team):
                    player, team = player_team
                    age_factor = 25 - getattr(player, 'age', 25)  # Younger = higher potential
                    potential = getattr(player, 'potential', 75)
                    current_rating = getattr(player, 'overall_rating', lambda: 70)() if callable(getattr(player, 'overall_rating', None)) else 70
                    return age_factor * 2 + potential + current_rating * 0.5
                
                sorted_players = sorted(young_players, key=get_breakout_potential, reverse=True)[:10]  # Top 10
                
                for rank, (player, team) in enumerate(sorted_players, 1):
                    age = getattr(player, 'age', 22)
                    potential = getattr(player, 'potential', 75)
                    current_rating = getattr(player, 'overall_rating', lambda: 70)() if callable(getattr(player, 'overall_rating', None)) else 70
                    
                    improvement = f"+{potential - current_rating} potential growth"
                    current_pace = f"{current_rating} overall rating"
                    projection = f"{min(potential, current_rating + 10)}-{potential} ceiling"
                    
                    player_data = (
                        rank, player.full_name, self._get_team_abbreviation(team.team_name), age,
                        improvement, current_pace, projection
                    )
                    tree.insert('', 'end', values=player_data)
                    
            else:  # goaltending
                # Sort goalies by save percentage approximation
                def get_goalie_score(player_team):
                    player, team = player_team
                    goaltending = getattr(player, 'goaltending', 10)
                    reflexes = getattr(player, 'reflexes', 10)
                    positioning = getattr(player, 'positioning', 10)
                    return goaltending + reflexes + positioning
                
                sorted_players = sorted(all_players, key=get_goalie_score, reverse=True)[:10]  # Top 10
                
                for rank, (player, team) in enumerate(sorted_players, 1):
                    games = getattr(player.stats, 'games_played', 15) if hasattr(player, 'stats') else 15
                    wins = getattr(player.stats, 'wins', 0) if hasattr(player, 'stats') else max(0, games - 8)
                    losses = getattr(player.stats, 'losses', 0) if hasattr(player, 'stats') else min(games - wins, 8)
                    
                    # Calculate goalie stats from attributes
                    goaltending = getattr(player, 'goaltending', 15)
                    gaa = round(max(1.5, 4.0 - (goaltending * 0.15)), 2)
                    sv_pct = f".{min(950, 850 + goaltending * 5)}"
                    shutouts = max(0, (goaltending - 15) // 3)
                    gsaa = round((goaltending - 15) * 0.8, 1)
                    
                    player_data = (
                        rank, player.full_name, self._get_team_abbreviation(team.team_name), games,
                        wins, losses, gaa, sv_pct, shutouts, gsaa
                    )
                    tree.insert('', 'end', values=player_data)
                    
        except Exception as e:
            # Fallback to show at least some data if there's an error
            print(f"Error loading player data for {category}: {e}")
            fallback_data = [(1, "Loading...", "---", "---", 0, 0, 0, 0, 0.0, 0, 0, 0)]
            for player_data in fallback_data:
                tree.insert('', 'end', values=player_data)
    
    def create_analytics_panel(self, parent, title, row, col):
        """Create an analytics panel"""
        panel = ttk.LabelFrame(parent, text=title, style='Panel.TLabelframe', padding=10)
        panel.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
        return panel
    
    def populate_trends_panel(self, panel):
        """Populate trends analysis panel with real game data"""
        try:
            # Calculate real trends from game data
            total_goals = 0
            total_games = 0
            total_teams = 0
            pp_efficiency_sum = 0
            overtime_games = 0
            shutouts = 0
            
            for team in self.parent.league.teams:
                if hasattr(team, 'league_name') and team.league_name == "National Hockey League":
                    total_teams += 1
                    team_games = max(team.games_played, 1)
                    total_games += team_games
                    
                    # Use team stats or calculate from wins/losses
                    team_goals = getattr(team, 'goals_for', team.wins * 3 + team.losses * 2)
                    total_goals += team_goals
                    
                    # Estimate PP efficiency (mock calculation)
                    pp_eff = min(30, 15 + (team.wins / max(team_games, 1)) * 10)
                    pp_efficiency_sum += pp_eff
                    
                    # Estimate overtime games
                    if hasattr(team, 'ot_losses'):
                        overtime_games += team.ot_losses
            
            if total_teams > 0:
                avg_goals_per_game = total_goals / max(total_games, 1)
                avg_pp_efficiency = pp_efficiency_sum / total_teams
                
                trends_data = [
                    ("Goals per game", f"{avg_goals_per_game:.2f} league average"),
                    ("Power play efficiency", f"{avg_pp_efficiency:.1f}% league average"),
                    ("Overtime games", f"{overtime_games} total this season"),
                    ("Games played", f"{total_games} total across {total_teams} teams"),
                ]
            else:
                # Fallback if no teams available
                trends_data = [
                    ("League data", "Loading team statistics..."),
                    ("Games played", "Season in progress"),
                    ("Statistics", "Calculating trends..."),
                ]
        
        except Exception as e:
            print(f"Error calculating trends: {e}")
            trends_data = [
                ("Data loading", "Calculating league trends..."),
                ("Season progress", "Games being tracked"),
                ("Statistics", "Real-time updates enabled"),
            ]
        
        for i, (metric, trend) in enumerate(trends_data):
            ttk.Label(panel, text=f"{metric}: {trend}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_outliers_panel(self, panel):
        """Populate statistical outliers panel with real game data"""
        try:
            outliers = []
            nhl_teams = [team for team in self.parent.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
            
            if nhl_teams:
                # Find team with best record
                best_team = max(nhl_teams, key=lambda t: t.wins)
                outliers.append(f"{best_team.team_name}: {best_team.wins} wins (league high)")
                
                # Find team with most losses
                worst_team = max(nhl_teams, key=lambda t: t.losses)
                if worst_team != best_team:
                    outliers.append(f"{worst_team.team_name}: {worst_team.losses} losses (league high)")
                
                # Find highest scoring team
                high_scoring = max(nhl_teams, key=lambda t: getattr(t, 'goals_for', t.wins * 3))
                goals_for = getattr(high_scoring, 'goals_for', high_scoring.wins * 3)
                outliers.append(f"{high_scoring.team_name}: {goals_for} goals scored")
                
                # Find team with best win percentage
                if nhl_teams:
                    best_pct_team = max(nhl_teams, key=lambda t: t.winning_percentage)
                    win_pct = best_pct_team.winning_percentage * 100
                    outliers.append(f"{best_pct_team.team_name}: {win_pct:.1f}% win rate")
                
                # Find top player if possible
                try:
                    all_players = []
                    for team in nhl_teams[:5]:  # Check first 5 teams for performance
                        if hasattr(team, 'roster') and team.roster:
                            for player in team.roster[:3]:  # Top 3 from each team
                                goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                                assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                                points = goals + assists
                                if points > 0:
                                    all_players.append((player, team, points))
                    
                    if all_players:
                        top_player, player_team, points = max(all_players, key=lambda x: x[2])
                        outliers.append(f"{player_team.team_name}: {top_player.full_name} with {points} points")
                        
                except Exception as e:
                    print(f"Error finding top player: {e}")
            
            # Fallback if no outliers found
            if not outliers:
                outliers = [
                    "Season in progress - tracking team performance",
                    "Player statistics being calculated",
                    "League leaders will appear as season progresses",
                    "Real-time statistical analysis active"
                ]
                
        except Exception as e:
            print(f"Error calculating outliers: {e}")
            outliers = [
                "Loading team performance data...",
                "Calculating statistical leaders...",
                "Real-time updates enabled",
                "Season statistics tracking active"
            ]
        
        for outlier in outliers:
            ttk.Label(panel, text=f"• {outlier}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_predictors_panel(self, panel):
        """Populate performance predictors panel"""
        predictors = [
            "Corsi leaders: 85% playoff rate",
            "Quality starts >60%: +12 pts avg",
            "PP% >25%: 78% top-8 finish",
            "Road record >0.600: Cup contender"
        ]
        
        for predictor in predictors:
            ttk.Label(panel, text=f"→ {predictor}", style='TLabel').pack(anchor='w', pady=2)
    
    def populate_metrics_panel(self, panel):
        """Populate advanced metrics panel"""
        metrics = [
            ("League PDO", "100.2"),
            ("Avg shooting %", "10.8%"),
            ("Avg save %", "0.908"),
            ("Goals/game", "6.1")
        ]
        
        for metric, value in metrics:
            frame = ttk.Frame(panel, style='Panel.TFrame')
            frame.pack(fill='x', pady=2)
            ttk.Label(frame, text=metric, style='TLabel').pack(side='left')
            ttk.Label(frame, text=value, style='Accent.TLabel').pack(side='right')
    
    def populate_trends_analysis(self):
        """Populate trends analysis tab"""
        # Clear existing content
        for widget in self.trends_container.winfo_children():
            widget.destroy()
        
        # Create trends display
        trends_text = tk.Text(self.trends_container, bg=self.parent.BG_COLOR, 
                             fg=self.parent.TEXT_COLOR, wrap='word', height=20)
        trends_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Get real trends data from actual teams
        trends_content = self.generate_real_trends_analysis()
        
        trends_text.insert(1.0, trends_content)
        trends_text.config(state='disabled')
    
    def generate_real_trends_analysis(self):
        """Generate trends analysis from real team data"""
        try:
            # Get real teams
            teams = []
            if hasattr(self.parent, 'league') and hasattr(self.parent.league, 'teams'):
                teams = [team for team in self.parent.league.teams 
                        if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
            
            if not teams:
                teams = self.get_fallback_teams()
            
            # Calculate league-wide statistics
            total_goals = sum(getattr(team, 'goals_for', 0) for team in teams)
            total_games = sum(getattr(team, 'games_played', 0) for team in teams)
            avg_goals_per_game = total_goals / max(1, total_games)
            
            # Find hot and cold teams
            hot_teams = sorted(teams, key=lambda t: t.wins * 2 + getattr(t, 'ot_losses', 0), reverse=True)[:3]
            cold_teams = sorted(teams, key=lambda t: t.wins * 2 + getattr(t, 'ot_losses', 0))[:3]
            
            # Generate analysis content
            content = f"""LEAGUE TRENDS ANALYSIS
===================

Current League Statistics:
• Average goals per game: {avg_goals_per_game:.2f}
• Total teams analyzed: {len(teams)}
• Season progress: Early season analysis

Team Performance Leaders:
🔥 Top Performing Teams:"""
            
            for i, team in enumerate(hot_teams, 1):
                points = team.wins * 2 + getattr(team, 'ot_losses', 0)
                goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
                content += f"\n   {i}. {team.team_name} ({team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}, {points} pts, {goal_diff:+d} goal diff)"
            
            content += f"\n\n❄️ Teams Needing Improvement:"
            for i, team in enumerate(cold_teams, 1):
                points = team.wins * 2 + getattr(team, 'ot_losses', 0)
                goal_diff = getattr(team, 'goals_for', 0) - getattr(team, 'goals_against', 0)
                content += f"\n   {i}. {team.team_name} ({team.wins}-{team.losses}-{getattr(team, 'ot_losses', 0)}, {points} pts, {goal_diff:+d} goal diff)"
            
            content += f"""

Statistical Trends:
• League scoring pace tracking well
• Competitive balance across teams
• Goal differential ranges from {min(getattr(t, 'goals_for', 0) - getattr(t, 'goals_against', 0) for t in teams):+d} to {max(getattr(t, 'goals_for', 0) - getattr(t, 'goals_against', 0) for t in teams):+d}

Analysis Notes:
• Data reflects current team standings and performance
• Trends will become more meaningful as season progresses
• Team momentum can shift rapidly in hockey
"""
            
            return content
            
        except Exception as e:
            print(f"Error generating trends analysis: {e}")
            return """LEAGUE TRENDS ANALYSIS
===================

Real-time trends analysis is being calculated from current team data.
Please check back after more games have been played for detailed trends.

Current data sources:
• Team standings and records
• Goal differentials
• Win/loss patterns

Analysis will be updated as the season progresses.
"""
        
        trends_text.insert('1.0', trends_content)
        trends_text.config(state='disabled')
    
    def populate_division_analysis(self):
        """Populate division analysis tab"""
        # Clear existing content
        for widget in self.division_container.winfo_children():
            widget.destroy()
        
        division = self.division_view.get()
        analysis_type = self.div_analysis_type.get()
        
        # Create division display based on selection
        if analysis_type == "Standings":
            self.create_division_standings(self.division_container, division)
        elif analysis_type == "Head-to-Head":
            self.create_head_to_head_analysis(self.division_container, division)
        else:
            # Default to standings
            self.create_division_standings(self.division_container, division)
    
    def create_division_standings(self, parent, division):
        """Create division-specific standings using real team data"""
        # Get real teams for this division
        division_teams = []
        try:
            if hasattr(self.parent, 'league') and hasattr(self.parent.league, 'teams'):
                all_teams = [team for team in self.parent.league.teams 
                           if hasattr(team, 'league_name') and team.league_name == "National Hockey League"]
                
                # For now, take any NHL teams and group them by division placeholder
                # In a real implementation, teams would have division attributes
                division_teams = all_teams[:4]  # Take first 4 for this division
            
            if not division_teams:
                fallback_teams = self.get_fallback_teams()
                division_teams = fallback_teams[:4]
                
        except Exception as e:
            print(f"Error getting division teams: {e}")
            division_teams = self.get_fallback_teams()[:4]
        
        # Convert teams to standings format
        divisions_data = {
            division: []
        }
        
        for team in division_teams:
            team_data = (
                team.team_name,
                team.wins,
                team.losses,
                getattr(team, 'ot_losses', 0),
                team.wins * 2 + getattr(team, 'ot_losses', 0)  # Points
            )
            divisions_data[division].append(team_data)
        
        # Sort by points
        divisions_data[division].sort(key=lambda x: x[4], reverse=True)
        
        # Create table
        columns = {
            'team': ('Team', 200),
            'w': ('W', 50),
            'l': ('L', 50),
            'otl': ('OTL', 50),
            'pts': ('PTS', 60)
        }
        
        tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                           show='headings', height=15)
        
        for col_id, (header, width) in columns.items():
            tree.heading(col_id, text=header, anchor='center')
            tree.column(col_id, width=width, anchor='center')
        
        # Add data
        if division in divisions_data:
            for team_data in divisions_data[division]:
                tree.insert('', 'end', values=team_data)
        
        tree.pack(fill='both', expand=True, padx=10, pady=10)
    
    def create_head_to_head_analysis(self, parent, division):
        """Create head-to-head analysis with real division data"""
        try:
            # Create container for head-to-head matrix
            container = ttk.Frame(parent)
            container.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Title
            title_label = ttk.Label(container, text=f"{division} Head-to-Head Records", 
                                   style='Title.TLabel')
            title_label.pack(pady=(0, 10))
            
            # Get teams from this division
            division_teams = []
            for team in self.parent.league.teams:
                if (hasattr(team, 'league_name') and team.league_name == "National Hockey League" and
                    hasattr(team, 'division') and division.lower() in team.division.lower()):
                    division_teams.append(team)
            
            if not division_teams:
                # Fallback: show a few NHL teams
                division_teams = [team for team in self.parent.league.teams 
                                if hasattr(team, 'league_name') and team.league_name == "National Hockey League"][:4]
            
            if division_teams:
                # Create simple head-to-head grid
                info_text = f"Teams in division: {len(division_teams)}\n\n"
                info_text += "Season Records:\n"
                
                for team in division_teams[:6]:  # Limit to 6 teams for display
                    record = team.record_string
                    points = team.points
                    info_text += f"• {team.team_name}: {record} ({points} pts)\n"
                
                info_text += f"\nNote: Detailed head-to-head matchup data will be available as the season progresses."
                
                info_label = ttk.Label(container, text=info_text, style='TLabel', justify='left')
                info_label.pack(anchor='w', padx=20)
            else:
                ttk.Label(container, text="Division data loading...", 
                         style='TLabel').pack(expand=True)
                         
        except Exception as e:
            print(f"Error creating head-to-head analysis: {e}")
            ttk.Label(parent, text="Head-to-head analysis initializing...", 
                     style='TLabel').pack(expand=True)
    
    def load_all_players_data(self, category):
        """Load all players data for pagination"""
        try:
            all_players = []
            
            # Collect all players from all teams
            for team in self.parent.league.teams:
                if hasattr(team, 'roster') and team.roster:
                    for player in team.roster:
                        if category == "goaltending":
                            # Only include goalies for goaltending stats
                            if hasattr(player, 'primary_position') and 'G' in str(player.primary_position):
                                all_players.append((player, team))
                        else:
                            # Include all non-goalies for other categories
                            if not (hasattr(player, 'primary_position') and 'G' in str(player.primary_position)):
                                all_players.append((player, team))
            
            # Sort players based on category
            if category == "scoring":
                def get_points(player_team):
                    player, team = player_team
                    goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                    assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                    return goals + assists
                sorted_players = sorted(all_players, key=get_points, reverse=True)
                
            elif category == "advanced":
                def get_advanced_score(player_team):
                    player, team = player_team
                    shooting = getattr(player, 'shooting', 10)
                    overall = getattr(player, 'overall_rating', lambda: 75)() if callable(getattr(player, 'overall_rating', None)) else 75
                    return shooting + (overall * 0.1)
                sorted_players = sorted(all_players, key=get_advanced_score, reverse=True)
                
            elif category == "breakout":
                young_players = [(p, t) for p, t in all_players if getattr(p, 'age', 25) <= 23]
                def get_breakout_potential(player_team):
                    player, team = player_team
                    age_factor = 25 - getattr(player, 'age', 25)
                    potential = getattr(player, 'potential', 75)
                    current_rating = getattr(player, 'overall_rating', lambda: 70)() if callable(getattr(player, 'overall_rating', None)) else 70
                    return age_factor * 2 + potential + current_rating * 0.5
                sorted_players = sorted(young_players, key=get_breakout_potential, reverse=True)
                
            else:  # goaltending
                def get_goalie_score(player_team):
                    player, team = player_team
                    goaltending = getattr(player, 'goaltending', 10)
                    reflexes = getattr(player, 'reflexes', 10)
                    positioning = getattr(player, 'positioning', 10)
                    return goaltending + reflexes + positioning
                sorted_players = sorted(all_players, key=get_goalie_score, reverse=True)
            
            # Store sorted players
            self.pagination_data[category]['all_players'] = sorted_players
            self.pagination_data[category]['total_players'] = len(sorted_players)
            
        except Exception as e:
            print(f"Error loading all players data for {category}: {e}")
            self.pagination_data[category]['all_players'] = []
            self.pagination_data[category]['total_players'] = 0
    
    def update_page_display(self, category):
        """Update the display for current page"""
        data = self.pagination_data[category]
        current_page = data['current_page']
        per_page = data['players_per_page']
        total_players = data['total_players']
        
        if total_players == 0:
            return
            
        # Calculate total pages
        total_pages = max(1, (total_players + per_page - 1) // per_page)
        
        # Ensure current page is valid
        if current_page > total_pages:
            current_page = total_pages
            data['current_page'] = current_page
        elif current_page < 1:
            current_page = 1
            data['current_page'] = current_page
        
        # Calculate start and end indices
        start_idx = (current_page - 1) * per_page
        end_idx = min(start_idx + per_page, total_players)
        
        # Update page label
        page_text = f"Showing {start_idx + 1}-{end_idx} of {total_players} players"
        data['page_label'].config(text=page_text)
        
        # Update page entry
        data['page_entry'].delete(0, tk.END)
        data['page_entry'].insert(0, str(current_page))
        
        # Enable/disable buttons
        buttons = data['buttons']
        buttons['first']['state'] = 'disabled' if current_page == 1 else 'normal'
        buttons['prev']['state'] = 'disabled' if current_page == 1 else 'normal'
        buttons['next']['state'] = 'disabled' if current_page == total_pages else 'normal'
        buttons['last']['state'] = 'disabled' if current_page == total_pages else 'normal'
        
        # Clear and populate tree with current page data
        tree = data['tree']
        for item in tree.get_children():
            tree.delete(item)
        
        page_players = data['all_players'][start_idx:end_idx]
        
        # Add players to tree with proper ranking
        for i, (player, team) in enumerate(page_players):
            rank = start_idx + i + 1
            
            if category == "scoring":
                goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else getattr(player, 'goals', 0)
                assists = getattr(player.stats, 'assists', 0) if hasattr(player, 'stats') else getattr(player, 'assists', 0)
                games = getattr(player.stats, 'games_played', 0) if hasattr(player, 'stats') else 0
                points = goals + assists
                ppg = round(points / max(games, 1), 2)
                plus_minus = getattr(player.stats, 'plus_minus', 0) if hasattr(player, 'stats') else 0
                pim = getattr(player.stats, 'pim', 0) if hasattr(player, 'stats') else 0
                shots = getattr(player.stats, 'shots', 0) if hasattr(player, 'stats') else 0
                
                position = str(getattr(player, 'primary_position', 'F'))
                if hasattr(player, 'primary_position') and hasattr(player.primary_position, 'value'):
                    position = player.primary_position.value
                
                player_data = (
                    rank, player.full_name, self._get_team_abbreviation(team.team_name), position,
                    games, goals, assists, points, ppg, plus_minus, pim, shots
                )
                
            elif category == "advanced":
                games = getattr(player.stats, 'games_played', 0) if hasattr(player, 'stats') else 0
                
                corsi_for = f"{round(50 + getattr(player, 'offensive_awareness', 10) * 0.5, 1)}%"
                expected_goals = round(getattr(player, 'shooting', 10) * 0.8, 1)
                shooting_pct = f"{round(getattr(player, 'shooting_accuracy', 10) * 0.8, 1)}%"
                pdo = round(100 + getattr(player, 'luck', 0) * 2, 1) if hasattr(player, 'luck') else 100.0
                zone_starts = f"{round(50 + getattr(player, 'positioning', 10) * 0.3, 1)}%"
                
                position = str(getattr(player, 'primary_position', 'F'))
                if hasattr(player, 'primary_position') and hasattr(player.primary_position, 'value'):
                    position = player.primary_position.value
                
                player_data = (
                    rank, player.full_name, self._get_team_abbreviation(team.team_name), position,
                    games, corsi_for, expected_goals, shooting_pct, pdo, zone_starts
                )
                
            elif category == "breakout":
                age = getattr(player, 'age', 22)
                potential = getattr(player, 'potential', 75)
                current_rating = getattr(player, 'overall_rating', lambda: 70)() if callable(getattr(player, 'overall_rating', None)) else 70
                
                improvement = f"+{potential - current_rating} potential growth"
                current_pace = f"{current_rating} overall rating"
                projection = f"{min(potential, current_rating + 10)}-{potential} ceiling"
                
                player_data = (
                    rank, player.full_name, self._get_team_abbreviation(team.team_name), age,
                    improvement, current_pace, projection
                )
                
            else:  # goaltending
                games = getattr(player.stats, 'games_played', 15) if hasattr(player, 'stats') else 15
                wins = getattr(player.stats, 'wins', 0) if hasattr(player, 'stats') else max(0, games - 8)
                losses = getattr(player.stats, 'losses', 0) if hasattr(player, 'stats') else min(games - wins, 8)
                
                goaltending = getattr(player, 'goaltending', 15)
                gaa = round(max(1.5, 4.0 - (goaltending * 0.15)), 2)
                sv_pct = f".{min(950, 850 + goaltending * 5)}"
                shutouts = max(0, (goaltending - 15) // 3)
                gsaa = round((goaltending - 15) * 0.8, 1)
                
                player_data = (
                    rank, player.full_name, self._get_team_abbreviation(team.team_name), games,
                    wins, losses, gaa, sv_pct, shutouts, gsaa
                )
            
            tree.insert('', 'end', values=player_data)
    
    def go_to_page(self, category, page):
        """Navigate to specific page"""
        data = self.pagination_data[category]
        total_pages = max(1, (data['total_players'] + data['players_per_page'] - 1) // data['players_per_page'])
        
        if 1 <= page <= total_pages:
            data['current_page'] = page
            self.update_page_display(category)
    
    def go_to_last_page(self, category):
        """Navigate to last page"""
        data = self.pagination_data[category]
        total_pages = max(1, (data['total_players'] + data['players_per_page'] - 1) // data['players_per_page'])
        self.go_to_page(category, total_pages)
    
    def go_to_page_from_entry(self, category, entry):
        """Navigate to page from entry field"""
        try:
            page = int(entry.get())
            self.go_to_page(category, page)
        except ValueError:
            # Reset entry to current page if invalid input
            data = self.pagination_data[category]
            entry.delete(0, tk.END)
            entry.insert(0, str(data['current_page']))
    
    def change_per_page(self, category, new_per_page_str):
        """Change number of players per page"""
        data = self.pagination_data[category]
        old_per_page = data['players_per_page']
        
        # Handle "All" option
        if new_per_page_str == "All":
            new_per_page = data['total_players']
        else:
            new_per_page = int(new_per_page_str)
        
        # Calculate what the current page should be with new per_page
        current_start_player = (data['current_page'] - 1) * old_per_page + 1
        new_page = max(1, (current_start_player + new_per_page - 1) // new_per_page)
        
        data['players_per_page'] = new_per_page
        data['current_page'] = new_page
        
        self.update_page_display(category)
    
    def update_player_leaders(self, event=None):
        """Update player leaders based on current filter settings"""
        try:
            # Get current tab
            current_tab = self.leaders_notebook.tab(self.leaders_notebook.select(), "text")
            
            # Determine category from tab name
            category_map = {
                "Scoring Leaders": "scoring",
                "Advanced Stats": "advanced", 
                "Breakout Players": "breakout",
                "Goaltending": "goaltending"
            }
            
            category = category_map.get(current_tab, "scoring")
            
            # Reload data and refresh pagination
            if hasattr(self, 'pagination_data') and category in self.pagination_data:
                self.load_all_players_data(category)
                self.update_page_display(category)
                
                # Update status with current filter info
                if hasattr(self, 'status_label'):
                    filter_text = "All Players"
                    if hasattr(self, 'position_filter') and self.position_filter.get() != "All":
                        filter_text = f"{self.position_filter.get()} Players"
                    
                    total_players = self.pagination_data[category]['total_players']
                    self.status_label.config(text=f"Player Leaders - {current_tab} ({filter_text}) - {total_players} total players")
                    
        except Exception as e:
            print(f"Error updating player leaders: {e}")
            # Don't crash the UI if there's an error
    
    def update_trends_analysis(self, event=None):
        """Update trends analysis"""
        self.populate_trends_analysis()
    
    def update_division_analysis(self, event=None):
        """Update division analysis"""
        self.populate_division_analysis()
    
    def refresh_analytics_dashboard(self):
        """Refresh analytics dashboard"""
        # Would refresh all analytics panels
        pass
    
    def refresh_records_data(self):
        """Refresh all records data"""
        try:
            self._populate_season_records()
            self._populate_career_records()
            self._populate_current_leaders()
            self._populate_record_chase()
            self._populate_achievements()
        except Exception as e:
            print(f"Error refreshing records data: {e}")
    
    def _populate_season_records(self):
        """Populate season records display with current player comparisons"""
        try:
            # Clear existing content
            for widget in self.season_scrollable_frame.winfo_children():
                widget.destroy()
            
            record_manager = self.parent.game_manager.record_manager
            
            # Get current league for player comparisons
            league = getattr(self.parent.game_manager, 'league', None)
            current_leaders = {}
            
            if league and hasattr(league, 'teams'):
                # Find current leaders for each record type
                all_players = []
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        all_players.extend([(player, team.team_name) for player in team.roster])
                
                if all_players:
                    # Calculate current leaders
                    goals_leader = max(all_players, key=lambda x: getattr(x[0], 'goals', 0))
                    assists_leader = max(all_players, key=lambda x: getattr(x[0], 'assists', 0))
                    points_leader = max(all_players, key=lambda x: getattr(x[0], 'goals', 0) + getattr(x[0], 'assists', 0))
                    wins_leader = max(all_players, key=lambda x: getattr(x[0], 'wins', 0) if hasattr(x[0], 'wins') else 0)
                    shutouts_leader = max(all_players, key=lambda x: getattr(x[0], 'shutouts', 0) if hasattr(x[0], 'shutouts') else 0)
                    
                    current_leaders = {
                        'single_season_goals': (goals_leader[0], getattr(goals_leader[0], 'goals', 0)),
                        'single_season_assists': (assists_leader[0], getattr(assists_leader[0], 'assists', 0)),
                        'single_season_points': (points_leader[0], getattr(points_leader[0], 'goals', 0) + getattr(points_leader[0], 'assists', 0)),
                        'single_season_wins': (wins_leader[0], getattr(wins_leader[0], 'wins', 0) if hasattr(wins_leader[0], 'wins') else 0),
                        'single_season_shutouts': (shutouts_leader[0], getattr(shutouts_leader[0], 'shutouts', 0) if hasattr(shutouts_leader[0], 'shutouts') else 0)
                    }
            
            # Season record categories
            season_categories = [
                ("🥅 Scoring Records", ["single_season_goals", "single_season_assists", "single_season_points"]),
                ("🏒 Goaltending Records", ["single_season_wins", "single_season_shutouts"]),
            ]
            
            row = 0
            for category_name, records in season_categories:
                # Category header
                header = ttk.Label(self.season_scrollable_frame, text=category_name,
                                  font=(self.parent.FONT_FAMILY, 14, 'bold'),
                                  foreground=self.parent.ACCENT_COLOR,
                                  background=self.parent.CONTENT_BG)
                header.grid(row=row, column=0, columnspan=4, sticky="w", pady=(15, 10), padx=10)
                row += 1
                
                # Records in this category
                for record_type in records:
                    record_display = record_manager.nhl_records.format_record_display(record_type)
                    if record_display and "No record found" not in record_display:
                        # Clean up display name
                        display_name = record_type.replace("_", " ").replace("single season ", "").title()
                        
                        # Record name
                        name_label = ttk.Label(self.season_scrollable_frame, text=f"{display_name}:",
                                              font=(self.parent.FONT_FAMILY, 11),
                                              foreground=self.parent.TEXT_COLOR,
                                              background=self.parent.CONTENT_BG)
                        name_label.grid(row=row, column=0, sticky="w", padx=(30, 10), pady=2)
                        
                        # NHL Record value
                        value_label = ttk.Label(self.season_scrollable_frame, text=record_display,
                                               font=(self.parent.FONT_FAMILY, 11, 'bold'),
                                               foreground='#FFD700',  # Gold color
                                               background=self.parent.CONTENT_BG)
                        value_label.grid(row=row, column=1, sticky="w", pady=2, padx=(0, 20))
                        
                        # Current season leader comparison
                        if record_type in current_leaders:
                            player, current_value = current_leaders[record_type]
                            if current_value > 0:
                                leader_text = f"Current Leader: {getattr(player, 'full_name', 'Unknown')} ({current_value})"
                                
                                # Get NHL record value for comparison
                                nhl_record_value = record_manager.nhl_records.season_records[record_type].value
                                percentage = (current_value / nhl_record_value) * 100 if nhl_record_value > 0 else 0
                                
                                if percentage >= 50:
                                    color = '#FFD700'  # Gold if close to record
                                elif percentage >= 25:
                                    color = '#FFA500'  # Orange if making progress
                                else:
                                    color = '#B0B0B0'  # Gray for normal
                                
                                leader_label = ttk.Label(self.season_scrollable_frame, text=leader_text,
                                                        font=(self.parent.FONT_FAMILY, 9),
                                                        foreground=color,
                                                        background=self.parent.CONTENT_BG)
                                leader_label.grid(row=row, column=2, sticky="w", pady=2)
                        
                        row += 1
                
        except Exception as e:
            print(f"Error populating season records: {e}")
    
    def _populate_career_records(self):
        """Populate career records display with current player comparisons"""
        try:
            # Clear existing content
            for widget in self.career_scrollable_frame.winfo_children():
                widget.destroy()
            
            record_manager = self.parent.game_manager.record_manager
            
            # Get current league for player comparisons
            league = getattr(self.parent.game_manager, 'league', None)
            current_leaders = {}
            
            if league and hasattr(league, 'teams'):
                # Find current leaders for each record type
                all_players = []
                for team in league.teams:
                    if hasattr(team, 'roster'):
                        all_players.extend([(player, team.team_name) for player in team.roster])
                
                if all_players:
                    # Calculate current career leaders
                    career_goals_leader = max(all_players, key=lambda x: getattr(x[0], 'career_goals', 0))
                    career_assists_leader = max(all_players, key=lambda x: getattr(x[0], 'career_assists', 0))
                    career_points_leader = max(all_players, key=lambda x: getattr(x[0], 'career_points', 0))
                    career_wins_leader = max(all_players, key=lambda x: getattr(x[0], 'career_wins', 0) if hasattr(x[0], 'career_wins') else 0)
                    career_shutouts_leader = max(all_players, key=lambda x: getattr(x[0], 'career_shutouts', 0) if hasattr(x[0], 'career_shutouts') else 0)
                    
                    current_leaders = {
                        'career_goals': (career_goals_leader[0], getattr(career_goals_leader[0], 'career_goals', 0)),
                        'career_assists': (career_assists_leader[0], getattr(career_assists_leader[0], 'career_assists', 0)),
                        'career_points': (career_points_leader[0], getattr(career_points_leader[0], 'career_points', 0)),
                        'career_wins': (career_wins_leader[0], getattr(career_wins_leader[0], 'career_wins', 0) if hasattr(career_wins_leader[0], 'career_wins') else 0),
                        'career_shutouts': (career_shutouts_leader[0], getattr(career_shutouts_leader[0], 'career_shutouts', 0) if hasattr(career_shutouts_leader[0], 'career_shutouts') else 0)
                    }
            
            # Career record categories
            career_categories = [
                ("🎯 Career Scoring", ["career_goals", "career_assists", "career_points"]),
                ("🥅 Career Goaltending", ["career_wins", "career_shutouts"]),
            ]
            
            row = 0
            for category_name, records in career_categories:
                # Category header
                header = ttk.Label(self.career_scrollable_frame, text=category_name,
                                  font=(self.parent.FONT_FAMILY, 14, 'bold'),
                                  foreground=self.parent.ACCENT_COLOR,
                                  background=self.parent.CONTENT_BG)
                header.grid(row=row, column=0, columnspan=4, sticky="w", pady=(15, 10), padx=10)
                row += 1
                
                # Records in this category
                for record_type in records:
                    record_display = record_manager.nhl_records.format_record_display(record_type)
                    if record_display and "No record found" not in record_display:
                        # Clean up display name
                        display_name = record_type.replace("_", " ").replace("career ", "").title()
                        
                        # Record name
                        name_label = ttk.Label(self.career_scrollable_frame, text=f"{display_name}:",
                                              font=(self.parent.FONT_FAMILY, 11),
                                              foreground=self.parent.TEXT_COLOR,
                                              background=self.parent.CONTENT_BG)
                        name_label.grid(row=row, column=0, sticky="w", padx=(30, 10), pady=2)
                        
                        # NHL Record value
                        value_label = ttk.Label(self.career_scrollable_frame, text=record_display,
                                               font=(self.parent.FONT_FAMILY, 11, 'bold'),
                                               foreground='#FFD700',  # Gold color
                                               background=self.parent.CONTENT_BG)
                        value_label.grid(row=row, column=1, sticky="w", pady=2, padx=(0, 20))
                        
                        # Current career leader comparison
                        if record_type in current_leaders:
                            player, current_value = current_leaders[record_type]
                            if current_value > 0:
                                leader_text = f"Current Leader: {getattr(player, 'full_name', 'Unknown')} ({current_value})"
                                
                                leader_label = ttk.Label(self.career_scrollable_frame, text=leader_text,
                                                        font=(self.parent.FONT_FAMILY, 9),
                                                        foreground='#B0B0B0',
                                                        background=self.parent.CONTENT_BG)
                                leader_label.grid(row=row, column=2, sticky="w", pady=2)
                        
                        row += 1
                
        except Exception as e:
            print(f"Error populating career records: {e}")
    
    def _populate_current_leaders(self):
        """Populate current season leaders with real game players"""
        try:
            # Clear existing items
            for item in self.current_leaders_tree.get_children():
                self.current_leaders_tree.delete(item)
            
            # Get current league data
            league = getattr(self.parent.game_manager, 'league', None)
            if not league or not hasattr(league, 'teams'):
                return
            
            # Collect all players with their current stats
            all_players = []
            for team in league.teams:
                if hasattr(team, 'roster'):
                    for player in team.roster:
                        all_players.append((player, team.team_name))
            
            if not all_players:
                return
            
            # Create comprehensive leaders for different stats
            stats_categories = [
                ("Goals", lambda p: getattr(p, 'goals', 0)),
                ("Assists", lambda p: getattr(p, 'assists', 0)),
                ("Points", lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0)),
                ("Games", lambda p: getattr(p, 'games_played', 0)),
                ("PIM", lambda p: getattr(p, 'penalty_minutes', 0)),
                ("Wins", lambda p: getattr(p, 'wins', 0) if hasattr(p, 'wins') else 0),
                ("Shutouts", lambda p: getattr(p, 'shutouts', 0) if hasattr(p, 'shutouts') else 0),
            ]
            
            rank = 1
            for stat_name, stat_func in stats_categories:
                # Sort players by this stat
                sorted_players = sorted(all_players, key=lambda x: stat_func(x[0]), reverse=True)
                
                # Add top 10 for each stat
                for i, (player, team) in enumerate(sorted_players[:10]):
                    value = stat_func(player)
                    if value > 0:  # Only show players with non-zero stats
                        # Determine position for display
                        position = getattr(player, 'primary_position', 'Unknown')
                        if hasattr(player, 'primary_position'):
                            position = str(player.primary_position).split('.')[-1] if '.' in str(player.primary_position) else str(player.primary_position)
                        
                        self.current_leaders_tree.insert("", "end", values=(
                            str(i + 1),  # Rank within this stat
                            getattr(player, 'full_name', 'Unknown'),
                            team,
                            position,
                            stat_name,
                            str(value)
                        ))
                
        except Exception as e:
            print(f"Error populating current leaders: {e}")
    
    def _populate_record_chase(self):
        """Populate record chase data with real players approaching records"""
        try:
            # Clear existing items
            for item in self.record_chase_tree.get_children():
                self.record_chase_tree.delete(item)
            
            # Get current league data and record manager
            league = getattr(self.parent.game_manager, 'league', None)
            record_manager = self.parent.game_manager.record_manager
            
            if not league or not hasattr(league, 'teams') or not record_manager:
                return
            
            # Collect all players with their current stats
            all_players = []
            for team in league.teams:
                if hasattr(team, 'roster'):
                    for player in team.roster:
                        all_players.append((player, team.team_name))
            
            if not all_players:
                return
            
            # Get NHL records to compare against
            nhl_records = record_manager.nhl_records
            
            # Track players approaching various records
            record_categories = [
                ("single_season_goals", "Goals", lambda p: getattr(p, 'goals', 0)),
                ("single_season_assists", "Assists", lambda p: getattr(p, 'assists', 0)),
                ("single_season_points", "Points", lambda p: getattr(p, 'goals', 0) + getattr(p, 'assists', 0)),
                ("single_season_wins", "Wins", lambda p: getattr(p, 'wins', 0) if hasattr(p, 'wins') else 0),
                ("single_season_shutouts", "Shutouts", lambda p: getattr(p, 'shutouts', 0) if hasattr(p, 'shutouts') else 0),
            ]
            
            chase_data = []
            
            for record_type, display_name, stat_func in record_categories:
                # Get the NHL record for this category
                if record_type in nhl_records.season_records:
                    record_info = nhl_records.season_records[record_type]
                    target_value = record_info.value
                    
                    # Find players with significant progress toward this record
                    for player, team in all_players:
                        current_value = stat_func(player)
                        
                        if current_value > 0:  # Only consider players with some progress
                            percentage = (current_value / target_value) * 100
                            difference = target_value - current_value
                            
                            # Show players who are at least 25% toward the record
                            if percentage >= 25.0:
                                chase_data.append({
                                    'player_name': getattr(player, 'full_name', 'Unknown'),
                                    'team': team,
                                    'record_type': display_name,
                                    'current_value': current_value,
                                    'target_value': target_value,
                                    'difference': difference,
                                    'percentage': percentage,
                                    'position': getattr(player, 'primary_position', 'Unknown')
                                })
            
            # Sort by percentage (closest to record first)
            chase_data.sort(key=lambda x: x['percentage'], reverse=True)
            
            # Add top 20 record chasers
            for i, chase_info in enumerate(chase_data[:20]):
                position = chase_info['position']
                if hasattr(chase_info['position'], 'name'):
                    position = str(chase_info['position']).split('.')[-1]
                
                self.record_chase_tree.insert("", "end", values=(
                    str(i + 1),
                    chase_info['player_name'],
                    chase_info['team'],
                    position,
                    chase_info['record_type'],
                    str(chase_info['current_value']),
                    str(chase_info['target_value']),
                    str(chase_info['difference']),
                    f"{chase_info['percentage']:.1f}%"
                ))
                
        except Exception as e:
            print(f"Error populating record chase: {e}")
    
    def _populate_achievements(self):
        """Populate recent achievements with real game data"""
        try:
            # Clear existing items
            for item in self.achievements_tree.get_children():
                self.achievements_tree.delete(item)
            
            record_manager = self.parent.game_manager.record_manager
            
            # Get recent records broken in the game
            recent_records = record_manager.get_recent_records(20)
            
            if recent_records:
                for record in recent_records:
                    # Format record type for display
                    record_type_display = record['record_type'].replace('_', ' ').title()
                    
                    # Get previous record holder info if available
                    previous_info = "Previous Record"
                    if 'previous_value' in record:
                        previous_info = f"Previous: {record['previous_value']}"
                    
                    self.achievements_tree.insert("", "end", values=(
                        record.get('timestamp', 'Unknown')[:10],  # Just date part
                        record['player_name'],
                        record['team'],
                        record_type_display,
                        str(record['new_value']),
                        previous_info
                    ))
            else:
                # Show placeholder message if no records have been broken yet
                self.achievements_tree.insert("", "end", values=(
                    "N/A",
                    "No records broken yet",
                    "Play games to see achievements!",
                    "",
                    "",
                    ""
                ))
                
        except Exception as e:
            print(f"Error populating achievements: {e}")
            # Show error message in the tree
            self.achievements_tree.insert("", "end", values=(
                "Error",
                "Could not load achievements",
                str(e)[:50] + "..." if len(str(e)) > 50 else str(e),
                "",
                "",
                ""
            ))

    def create_analytics_dashboard_content(self, parent_frame):
        """Create analytics dashboard content"""
        # Title
        title_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        title_frame.pack(fill='x', pady=(0, 15))
        
        title_label = ttk.Label(title_frame, text="League Analytics Dashboard", 
                               style='Title.TLabel', font=(self.parent.FONT_FAMILY, 18, 'bold'))
        title_label.pack(side='left')
        
        # Key metrics frame
        metrics_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        metrics_frame.pack(fill='x', pady=(0, 15))
        
        # Calculate league-wide statistics
        if hasattr(self.parent, 'game_manager') and self.parent.game_manager.league:
            league = self.parent.game_manager.league
            
            # Total goals scored across league
            total_goals = 0
            total_games = 0
            avg_attendance = 0
            
            for team in league.teams:
                team_goals = sum(getattr(p, 'goals', 0) for p in team.roster + team.ahl_roster)
                total_goals += team_goals
                total_games += team.games_played if hasattr(team, 'games_played') else 0
                avg_attendance += getattr(team, 'avg_attendance', 15000)
            
            avg_attendance = avg_attendance / len(league.teams) if league.teams else 0
            
            # Create metric cards
            self._create_metric_card(metrics_frame, "Total Goals", f"{total_goals:,}", "#4CAF50")
            self._create_metric_card(metrics_frame, "Games Played", f"{total_games:,}", "#2196F3")
            self._create_metric_card(metrics_frame, "Avg Attendance", f"{avg_attendance:,.0f}", "#FF9800")
            self._create_metric_card(metrics_frame, "Active Teams", f"{len(league.teams)}", "#9C27B0")
        
        # Charts placeholder
        charts_frame = ttk.LabelFrame(parent_frame, text="Performance Charts", style='Panel.TLabelframe')
        charts_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        chart_label = ttk.Label(charts_frame, text="📊 Advanced charts and visualizations would appear here", 
                               style='Content.TLabel')
        chart_label.pack(pady=50)
    
    def create_trends_analysis_content(self, parent_frame):
        """Create trends analysis content"""
        # Title
        title_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        title_frame.pack(fill='x', pady=(0, 15))
        
        title_label = ttk.Label(title_frame, text="League Trends Analysis", 
                               style='Title.TLabel', font=(self.parent.FONT_FAMILY, 18, 'bold'))
        title_label.pack(side='left')
        
        # Trends content
        trends_frame = ttk.LabelFrame(parent_frame, text="Current Trends", style='Panel.TLabelframe')
        trends_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        trends_text = tk.Text(trends_frame, height=20, wrap='word', 
                             bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                             font=(self.parent.FONT_FAMILY, 10), relief='flat')
        trends_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Sample trends content
        trends_content = """📈 LEAGUE TRENDS ANALYSIS

🏒 Scoring Trends:
• Goals per game trending upward
• Power play efficiency improving league-wide
• Goaltending save percentages stabilizing

👥 Player Development:
• Younger players getting more ice time
• Rookie impact players emerging
• Veteran leadership maintaining importance

📊 Team Performance:
• Balanced scoring becoming more valuable
• Special teams playing decisive role
• Home ice advantage factors

🎯 Emerging Patterns:
• Speed and skill emphasis increasing
• Analytics-driven decisions growing
• Player versatility highly valued

📋 Key Insights:
• Draft picks showing faster development
• Contract values adjusting to market
• International player influence growing"""
        
        trends_text.insert('1.0', trends_content)
        trends_text.config(state='disabled')
    
    def create_performance_insights_content(self, parent_frame):
        """Create performance insights content"""
        # Title
        title_frame = ttk.Frame(parent_frame, style='Panel.TFrame')
        title_frame.pack(fill='x', pady=(0, 15))
        
        title_label = ttk.Label(title_frame, text="Performance Insights", 
                               style='Title.TLabel', font=(self.parent.FONT_FAMILY, 18, 'bold'))
        title_label.pack(side='left')
        
        # Insights notebook
        insights_notebook = ttk.Notebook(parent_frame)
        insights_notebook.pack(fill='both', expand=True)
        
        # Team insights
        team_insights_frame = ttk.Frame(insights_notebook, style='Panel.TFrame', padding=10)
        insights_notebook.add(team_insights_frame, text="Team Analysis")
        
        team_text = tk.Text(team_insights_frame, height=15, wrap='word',
                           bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                           font=(self.parent.FONT_FAMILY, 10), relief='flat')
        team_text.pack(fill='both', expand=True)
        
        # Player insights
        player_insights_frame = ttk.Frame(insights_notebook, style='Panel.TFrame', padding=10)
        insights_notebook.add(player_insights_frame, text="Player Analysis")
        
        player_text = tk.Text(player_insights_frame, height=15, wrap='word',
                             bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                             font=(self.parent.FONT_FAMILY, 10), relief='flat')
        player_text.pack(fill='both', expand=True)
        
        # Sample insights
        team_content = """🏒 TEAM PERFORMANCE INSIGHTS

Top Performing Teams:
• Strong defensive core correlation with success
• Balanced scoring depth showing sustainability
• Special teams efficiency as differentiator

Areas for Improvement:
• Power play conversions below league average
• Penalty kill struggling against top units
• Goaltending consistency key factor

Competitive Balance:
• Salary cap creating parity
• Draft system promoting equality
• Coaching strategies evolving"""
        
        player_content = """⭐ PLAYER PERFORMANCE INSIGHTS

Standout Performers:
• Young players exceeding expectations
• Veterans maintaining elite production
• Goalies showing improved consistency

Development Patterns:
• Skill-based players adapting faster
• Physical development taking longer
• Mental game crucial for success

Market Trends:
• Two-way players in high demand
• Specialists finding niche roles
• Leadership qualities valued"""
        
        team_text.insert('1.0', team_content)
        team_text.config(state='disabled')
        
        player_text.insert('1.0', player_content)
        player_text.config(state='disabled')
    
    def _create_metric_card(self, parent, title, value, color):
        """Create a metric card widget"""
        card_frame = ttk.Frame(parent, style='Panel.TFrame', relief='solid')
        card_frame.pack(side='left', padx=5, pady=5, fill='both', expand=True)
        
        title_label = ttk.Label(card_frame, text=title, style='Content.TLabel', 
                               font=(self.parent.FONT_FAMILY, 10))
        title_label.pack(pady=(10, 0))
        
        value_label = ttk.Label(card_frame, text=value, style='Title.TLabel',
                               font=(self.parent.FONT_FAMILY, 16, 'bold'))
        value_label.pack(pady=(0, 10))
