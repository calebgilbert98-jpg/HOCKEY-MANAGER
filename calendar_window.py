import tkinter as tk
from tkinter import ttk
import calendar
from datetime import date, timedelta
from typing import Dict, List, Tuple

class CalendarWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(f"🗓️ Season Calendar - {self.parent.user_team.team_name}")
        self.geometry("1200x800")
        self.configure(background=parent.BG_COLOR)
        
        # Window setup
        self.resizable(True, True)
        self.transient(parent)
        
        # Current date tracking
        self.current_view_date = self.parent.current_date
        self.selected_date = None
        
        # Event data
        self.events_by_date = {}
        self._load_season_events()
        
        # Configure calendar styles
        self._configure_calendar_styles()
        
        # Create UI
        self._create_widgets()
        self._populate_calendar()
        
        # Add to parent's open windows
        self.parent.open_windows['calendar'] = self
        
        # Center window
        self.center_window()
        
    def center_window(self):
        """Center the window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def _configure_calendar_styles(self):
        """Configure calendar-specific button styles with highly distinct colors."""
        style = ttk.Style()
        
        # Home game style - Deep Blue
        style.configure('HomeGame.TButton',
                       background='#1565C0',  # Deep blue for home games
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('HomeGame.TButton',
                 background=[('active', '#0D47A1')])
                 
        # Away game style - Bright Cyan
        style.configure('AwayGame.TButton',
                       background='#00BCD4',  # Bright cyan for away games
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('AwayGame.TButton',
                 background=[('active', '#0097A7')])
                 
        # League games style - Slate Grey (other teams' games, no user game)
        style.configure('LeagueGames.TButton',
                       background='#546E7A',  # Slate grey for league games
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8))
        style.map('LeagueGames.TButton',
                 background=[('active', '#37474F')])
                 
        # Break days style - Dark Grey
        style.configure('BreakDay.TButton',
                       background='#424242',  # Dark grey for break days
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8))
        style.map('BreakDay.TButton',
                 background=[('active', '#212121')])
                 
        # All-Star event style - Bright Gold
        style.configure('AllStar.TButton',
                       background='#FFC107',  # Bright gold for All-Star events
                       foreground='black',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('AllStar.TButton',
                 background=[('active', '#FFB300')])
                 
        # Trade deadline style - Bright Red
        style.configure('TradeDeadline.TButton',
                       background='#E53935',  # Bright red for trade deadline
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('TradeDeadline.TButton',
                 background=[('active', '#C62828')])
                 
        # Today style - Hot Pink
        style.configure('Today.TButton',
                       background='#E91E63',  # Hot pink for today
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('Today.TButton',
                 background=[('active', '#AD1457')])
                 
        # Important event style - Bright Orange
        style.configure('ImportantEvent.TButton',
                       background='#FF5722',  # Bright orange for important events
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('ImportantEvent.TButton',
                 background=[('active', '#D84315')])
                 
        # Draft style - Purple
        style.configure('Draft.TButton',
                       background='#7B1FA2',  # Purple for draft events
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('Draft.TButton',
                 background=[('active', '#6A1B9A')])
                 
        # Free Agency style - Green
        style.configure('FreeAgency.TButton',
                       background='#388E3C',  # Green for free agency
                       foreground='white',
                       font=(self.parent.FONT_FAMILY, 8, 'bold'))
        style.map('FreeAgency.TButton',
                 background=[('active', '#2E7D32')])
        
    def _create_widgets(self):
        """Create the calendar interface."""
        # Main container
        main_frame = ttk.Frame(self, style='Panel.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header frame with navigation
        self._create_header(main_frame)
        
        # Content frame (calendar + details)
        content_frame = ttk.Frame(main_frame, style='Panel.TFrame')
        content_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Calendar frame (left side)
        calendar_frame = ttk.LabelFrame(content_frame, text="📅 Calendar View", 
                                       style='TitleBar.TFrame', padding=10)
        calendar_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Details frame (right side)
        details_frame = ttk.LabelFrame(content_frame, text="📋 Event Details", 
                                      style='TitleBar.TFrame', padding=10)
        details_frame.pack(side='right', fill='y', padx=(5, 0))
        details_frame.configure(width=300)
        
        # Create calendar grid
        self._create_calendar_grid(calendar_frame)
        
        # Create details panel
        self._create_details_panel(details_frame)
        
    def _create_header(self, parent):
        """Create header with navigation and month/year display."""
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))
        
        # Navigation buttons
        nav_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        nav_frame.pack(side='left')
        
        ttk.Button(nav_frame, text="◄◄ Prev Month", style='Menu.TButton',
                  command=self._prev_month).pack(side='left', padx=(0, 5))
        ttk.Button(nav_frame, text="Today", style='Menu.TButton',
                  command=self._go_to_today).pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Next Month ►►", style='Menu.TButton',
                  command=self._next_month).pack(side='left', padx=(5, 0))
        
        # Month/Year display
        self.month_year_label = ttk.Label(header_frame, text="", 
                                         style='Header.TLabel',
                                         font=(self.parent.FONT_FAMILY, 16, 'bold'))
        self.month_year_label.pack(side='right')
        
        # Legend with highly distinct colors
        legend_frame = ttk.Frame(header_frame, style='TitleBar.TFrame')
        legend_frame.pack()
        
        legend_items = [
            ("🏒 Home Game", "#1565C0"),      # Deep Blue
            ("✈️ Away Game", "#00BCD4"),      # Bright Cyan  
            ("🛑 Break Days", "#424242"),     # Dark Grey
            ("⭐ All-Star Events", "#FFC107"), # Bright Gold
            ("📈 Trade Deadline", "#E53935"), # Bright Red
            ("📅 Today", "#E91E63"),          # Hot Pink
            ("🎯 Draft & Free Agency", "#FF5722"), # Bright Orange
            ("🎄 Special Events", "#FF5722")  # Bright Orange
        ]
        
        # Create legend items in multiple rows (4 items per row for better spacing)
        for i, (text, color) in enumerate(legend_items):
            row = i // 4  # 4 items per row
            col = i % 4
            
            # Create colored square indicator with better visibility
            legend_item_frame = ttk.Frame(legend_frame, style='TitleBar.TFrame')
            legend_item_frame.grid(row=row, column=col, padx=12, pady=3, sticky='w')
            
            # Larger color indicator for better visibility
            color_indicator = tk.Label(legend_item_frame, text="●", 
                                     fg=color, bg=self.parent.BG_COLOR,
                                     font=(self.parent.FONT_FAMILY, 14, 'bold'))
            color_indicator.pack(side='left', padx=(0, 6))
            
            # Text label with consistent styling
            text_label = ttk.Label(legend_item_frame, text=text, style='Content.TLabel',
                                 font=(self.parent.FONT_FAMILY, 9))
            text_label.pack(side='left')
        
    def _create_calendar_grid(self, parent):
        """Create the calendar grid layout."""
        # Days of week header
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        header_frame = ttk.Frame(parent, style='TitleBar.TFrame')
        header_frame.pack(fill='x', pady=(0, 5))
        
        for i, day in enumerate(days):
            label = ttk.Label(header_frame, text=day[:3], style='Header.TLabel',
                            font=(self.parent.FONT_FAMILY, 12, 'bold'))
            label.grid(row=0, column=i, padx=1, pady=1, sticky='ew')
            header_frame.grid_columnconfigure(i, weight=1)
        
        # Calendar grid
        self.calendar_frame = ttk.Frame(parent, style='Panel.TFrame')
        self.calendar_frame.pack(fill='both', expand=True)
        
        # Configure grid weights
        for i in range(7):  # 7 columns (days of week)
            self.calendar_frame.grid_columnconfigure(i, weight=1)
        for i in range(6):  # 6 rows (max weeks in month)
            self.calendar_frame.grid_rowconfigure(i, weight=1)
            
        # Store day buttons for updates
        self.day_buttons = {}
        
    def _create_details_panel(self, parent):
        """Create the event details panel."""
        # Selected date label
        self.selected_date_label = ttk.Label(parent, text="Select a date", 
                                           style='Header.TLabel',
                                           font=(self.parent.FONT_FAMILY, 14, 'bold'))
        self.selected_date_label.pack(anchor='w', pady=(0, 10))
        
        # Events list
        events_frame = ttk.Frame(parent, style='Panel.TFrame')
        events_frame.pack(fill='both', expand=True)
        
        # Scrollable text widget for events
        self.events_text = tk.Text(events_frame, wrap='word', height=20, width=35,
                                  bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR,
                                  font=(self.parent.FONT_FAMILY, 10),
                                  relief='flat', borderwidth=0)
        
        scrollbar = ttk.Scrollbar(events_frame, orient='vertical', 
                                command=self.events_text.yview)
        self.events_text.configure(yscrollcommand=scrollbar.set)
        
        self.events_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Quick actions frame (dynamic - will be updated based on selected date)
        self.actions_frame = ttk.Frame(parent, style='Panel.TFrame')
        self.actions_frame.pack(fill='x', pady=(10, 0))
        
        # Initialize with default actions
        self._create_default_actions()
        
    def _create_default_actions(self):
        """Create default action buttons."""
        # Clear existing buttons
        for widget in self.actions_frame.winfo_children():
            widget.destroy()
            
        ttk.Button(self.actions_frame, text="🏒 View Game Details", style='TButton',
                  command=self._view_game_details).pack(fill='x', pady=2)
        ttk.Button(self.actions_frame, text="📊 Team Stats", style='TButton',
                  command=self._view_team_stats).pack(fill='x', pady=2)
        ttk.Button(self.actions_frame, text="📰 News & Updates", style='TButton',
                  command=self._view_news).pack(fill='x', pady=2)
                  
    def _create_trade_deadline_actions(self):
        """Create action buttons for trade deadline day."""
        # Clear existing buttons
        for widget in self.actions_frame.winfo_children():
            widget.destroy()
            
        # Trade Deadline Center button (prominent)
        ttk.Button(self.actions_frame, text="🚨 TRADE DEADLINE CENTER", style='TradeDeadline.TButton',
                  command=self._launch_trade_deadline_center).pack(fill='x', pady=2)
        ttk.Button(self.actions_frame, text="🔄 Trade Center", style='TButton',
                  command=self.parent.open_trade_window).pack(fill='x', pady=2)
        ttk.Button(self.actions_frame, text="📈 Market Analysis", style='TButton',
                  command=self._view_market_analysis).pack(fill='x', pady=2)
        ttk.Button(self.actions_frame, text="📰 Deadline News", style='TButton',
                  command=self._view_news).pack(fill='x', pady=2)
                  
    def _launch_trade_deadline_center(self):
        """Launch the Trade Deadline Center from calendar."""
        self.parent.open_trade_deadline_center()
        
    def _view_market_analysis(self):
        """Placeholder for market analysis - could open trade statistics."""
        # For now, redirect to trade window
        self.parent.open_trade_window()
        
    def _load_season_events(self):
        """Load all season events from the game data."""
        self.events_by_date.clear()
        
        # Load NHL calendar information from league
        self.nhl_calendar_info = self._get_nhl_calendar_info()
        
        # Load team games and NHL events
        for game_entry in self.parent.league.schedule:
            # Handle different schedule formats
            if isinstance(game_entry, dict):
                # New format: dictionary with date, home_team, away_team, etc.
                game_date = game_entry['date']
                home_team = game_entry['home_team']
                away_team = game_entry['away_team']
            elif isinstance(game_entry, (tuple, list)) and len(game_entry) >= 3:
                # Handle NHL special events in tuple format: (date, 'NHL_EVENT', event_data)
                if game_entry[1] == 'NHL_EVENT':
                    game_date = game_entry[0]
                    event_data = game_entry[2]  # The event data dictionary
                    event = {
                        'type': event_data['type'],
                        'title': event_data['title'],
                        'description': event_data['description'],
                        'importance': 'critical'
                    }
                    
                    if game_date not in self.events_by_date:
                        self.events_by_date[game_date] = []
                    self.events_by_date[game_date].append(event)
                    continue  # Skip to next entry
                
                # Regular game format: tuple/list with (date, home_team, away_team)
                game_date, home_team, away_team = game_entry[0], game_entry[1], game_entry[2]
            else:
                continue  # Skip malformed entries
            
            # Handle NHL special events (legacy format)
            if home_team == 'NHL_EVENT':
                event_data = away_team  # The event data dictionary
                event = {
                    'type': event_data['type'],
                    'title': event_data['title'],
                    'description': event_data['description'],
                    'importance': 'critical'
                }
                
                if game_date not in self.events_by_date:
                    self.events_by_date[game_date] = []
                self.events_by_date[game_date].append(event)
            
            # Handle regular team games - show ALL games (EHM/FM style)
            # User's games get high importance, others get normal
            else:
                is_user_game = self.parent.user_team in (home_team, away_team)
                
                if is_user_game:
                    is_home = self.parent.user_team == home_team
                    opponent = away_team if is_home else home_team
                    
                    event = {
                        'type': 'game',
                        'title': f"{'vs' if is_home else '@'} {opponent.team_name}",
                        'description': f"{'Home' if is_home else 'Away'} game against {opponent.team_name}",
                        'is_home': is_home,
                        'opponent': opponent,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_user_game': True,
                        'importance': 'high'
                    }
                    
                    # Check if this is a special game
                    if self._is_special_date(game_date):
                        event['importance'] = 'critical'
                else:
                    # Other teams' games - show compactly
                    home_name = home_team.team_name if hasattr(home_team, 'team_name') else str(home_team)
                    away_name = away_team.team_name if hasattr(away_team, 'team_name') else str(away_team)
                    
                    event = {
                        'type': 'game',
                        'title': f"{away_name} @ {home_name}",
                        'description': f"NHL game: {away_name} at {home_name}",
                        'is_home': None,
                        'opponent': None,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_user_game': False,
                        'importance': 'normal'
                    }
                
                if game_date not in self.events_by_date:
                    self.events_by_date[game_date] = []
                self.events_by_date[game_date].append(event)
        
        # NHL events are now loaded from the main schedule above
        # Only add break days and other calendar events
        self._add_break_days_and_holidays()
        
        # Add other important dates
        self._add_important_dates()
        
    def _get_season_year(self):
        """Get the season year (year the season starts) from the league.
        
        Falls back to deriving from current_date if league not available.
        The season_year is the year the season starts (e.g., 2024 for 2024-25).
        """
        try:
            if hasattr(self.parent, 'league') and hasattr(self.parent.league, 'season_year'):
                return self.parent.league.season_year
        except (AttributeError, TypeError):
            pass
        # Fallback: derive from current date
        # If we're in Jan-Sep, the season started last year
        current = self.parent.current_date
        if current.month >= 10:
            return current.year
        else:
            return current.year - 1
    
    def _is_special_date(self, game_date):
        """Check if a date represents a special game (holidays, rivalries, etc.)."""
        # Check for holiday games
        if (game_date.month == 12 and game_date.day == 25) or \
           (game_date.month == 1 and game_date.day == 1) or \
           (game_date.month == 11 and 22 <= game_date.day <= 28):  # Thanksgiving week
            return True
            
        # Check for season opener/closer
        # Use season_year (year season starts) to avoid year-boundary bugs
        season_year = self._get_season_year()
        season_start = date(season_year, 10, 8)
        season_end = date(season_year + 1, 4, 25)
        
        if abs((game_date - season_start).days) <= 7 or \
           abs((season_end - game_date).days) <= 7:
            return True
            
        return False
    
    def _get_nhl_calendar_info(self):
        """Get NHL calendar information from the league.
        
        Uses league.season_year and matches the dates used by the actual
        schedule generator in game_classes.py (_create_authentic_nhl_calendar).
        """
        season_year = self._get_season_year()
        
        # Match the real generator dates exactly:
        # - Thanksgiving: Nov 24 (season_year)
        # - Christmas: Dec 24-25 (season_year)  
        # - All-Star: Feb 5-11 (season_year + 1)
        # - Trade deadline: Mar 8 (season_year + 1)
        return {
            'all_star_break': (
                date(season_year + 1, 2, 5),
                date(season_year + 1, 2, 11)
            ),
            'trade_deadline': date(season_year + 1, 3, 8),
            'christmas_break': (
                date(season_year, 12, 24),
                date(season_year, 12, 25)
            ),
            'thanksgiving_break': (
                date(season_year, 11, 24),
                date(season_year, 11, 24)
            )
        }
    
    def _add_break_days_and_holidays(self):
        """Add break days and holiday periods (main events now come from schedule)."""
        if not self.nhl_calendar_info:
            return
        
        # All-Star break dates
        all_star_start, all_star_end = self.nhl_calendar_info['all_star_break']
        current_date = all_star_start
        
        # Add All-Star break days (main events now come from schedule)
        while current_date <= all_star_end:
            if current_date not in self.events_by_date:
                self.events_by_date[current_date] = []
                
            # Check if this date already has a main event from the schedule
            has_main_event = any(e['type'] in ['all_star_skills', 'all_star_game'] 
                               for e in self.events_by_date[current_date])
            
            # Only add break day if there's no main event
            if not has_main_event:
                event = {
                    'type': 'break_day',
                    'title': '🛑 All-Star Break',
                    'description': 'No regular season games scheduled',
                    'importance': 'medium'
                }
                self.events_by_date[current_date].append(event)
            
            current_date += timedelta(days=1)
        
        # Trade deadline now comes from the main schedule
        
        # Christmas break dates
        christmas_start, christmas_end = self.nhl_calendar_info['christmas_break']
        current_date = christmas_start
        
        while current_date <= christmas_end:
            if current_date.day == 25:  # Christmas Day
                event = {
                    'type': 'christmas',
                    'title': '🎄 Christmas Day',
                    'description': 'Special holiday games may be scheduled',
                    'importance': 'high'
                }
            else:
                event = {
                    'type': 'break_day',
                    'title': '🛑 Christmas Break',
                    'description': 'Reduced game schedule for holidays',
                    'importance': 'medium'
                }
            
            if current_date not in self.events_by_date:
                self.events_by_date[current_date] = []
            self.events_by_date[current_date].append(event)
            current_date += timedelta(days=1)
        
    def _add_important_dates(self):
        """Add important league dates and events (non-NHL calendar events).
        
        Uses league.season_year and matches the actual schedule generator dates.
        """
        season_year = self._get_season_year()
        
        important_dates = [
            (date(season_year, 10, 8), "🏒 Season Opener", "NHL regular season begins"),
            (date(season_year + 1, 1, 1), "🎊 New Year's Day", "Winter Classic and New Year games"),
            (date(season_year + 1, 2, 14), "❤️ Valentine's Day", "Special promotional games"),
            (date(season_year + 1, 4, 25), "🏁 Regular Season End", "End of regular season"),
            (date(season_year + 1, 4, 26), "🏆 Playoffs Begin", "Stanley Cup Playoffs start"),
            (date(season_year + 1, 6, 27), "🏒 Draft Day", "NHL Entry Draft"),
            (date(season_year + 1, 7, 1), "💰 Free Agency", "Free agency period begins")
        ]
        
        for event_date, title, description in important_dates:
            # Skip if we already have events for this date (avoid duplicates)
            if event_date in self.events_by_date:
                continue
                
            event = {
                'type': 'league_event',
                'title': title,
                'description': description,
                'importance': 'medium'
            }
            
            if event_date not in self.events_by_date:
                self.events_by_date[event_date] = []
            self.events_by_date[event_date].append(event)
    
    def _populate_calendar(self):
        """Populate the calendar with the current month."""
        # Clear existing buttons
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()
        self.day_buttons.clear()
        
        # Update month/year label
        month_name = calendar.month_name[self.current_view_date.month]
        self.month_year_label.config(text=f"{month_name} {self.current_view_date.year}")
        
        # Get calendar data
        cal = calendar.monthcalendar(self.current_view_date.year, self.current_view_date.month)
        
        # Create day buttons
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day == 0:  # Empty cell
                    continue
                    
                button_date = date(self.current_view_date.year, self.current_view_date.month, day)
                
                # Determine button style and text based on events
                button_text = str(day)
                button_style = 'Menu.TButton'
                
                # Check for events and determine priority styling
                events = self.events_by_date.get(button_date, [])
                
                # Priority order: Today > Games > All-Star > Trade Deadline > Break Days > Other
                if button_date == self.parent.current_date:
                    button_style = 'Today.TButton'
                    button_text += "\n📅"
                elif events:
                    # Check for games first (highest priority for user)
                    game_events = [e for e in events if e['type'] == 'game']
                    all_star_events = [e for e in events if e['type'] in ['all_star', 'all_star_skills', 'all_star_game']]
                    trade_deadline_events = [e for e in events if e['type'] == 'trade_deadline']
                    draft_events = [e for e in events if e['type'] in ['entry_draft', 'free_agency']]
                    break_events = [e for e in events if e['type'] == 'break_day']
                    christmas_events = [e for e in events if e['type'] == 'christmas']
                    
                    if game_events:
                        # Prioritize user's game; otherwise show league game count
                        user_games = [g for g in game_events if g.get('is_user_game', False)]
                        if user_games:
                            game = user_games[0]
                            if game['is_home']:
                                button_style = 'HomeGame.TButton'
                                button_text += "\n🏒"
                            else:
                                button_style = 'AwayGame.TButton'
                                button_text += "\n✈️"
                        else:
                            # No user game today - show how many league games
                            num_games = len(game_events)
                            button_style = 'LeagueGames.TButton'
                            button_text += f"\n{num_games} games"
                    elif all_star_events:
                        button_style = 'AllStar.TButton'
                        button_text += "\n⭐"
                    elif trade_deadline_events:
                        button_style = 'TradeDeadline.TButton'
                        button_text += "\n📈"
                    elif draft_events:
                        # Check specific draft event types
                        free_agency_events = [e for e in draft_events if 'free_agency' in e['type']]
                        if free_agency_events:
                            button_style = 'FreeAgency.TButton'
                            button_text += "\n💰"
                        else:
                            button_style = 'Draft.TButton'
                            button_text += "\n🎯"
                    elif christmas_events:
                        button_style = 'ImportantEvent.TButton'
                        button_text += "\n🎄"
                    elif break_events:
                        button_style = 'BreakDay.TButton'
                        button_text += "\n🛑"
                    else:
                        # Other important events
                        important_events = [e for e in events if e['importance'] in ['high', 'critical']]
                        if important_events:
                            button_style = 'ImportantEvent.TButton'
                            button_text += "\n⭐"
                    
                # Create button with direct color mapping for better visibility
                color_map = {
                    'HomeGame.TButton': '#1565C0',      # Deep Blue
                    'AwayGame.TButton': '#00BCD4',      # Bright Cyan
                    'LeagueGames.TButton': '#546E7A',   # Slate Grey
                    'BreakDay.TButton': '#424242',      # Dark Grey
                    'AllStar.TButton': '#FFC107',       # Bright Gold
                    'TradeDeadline.TButton': '#E53935', # Bright Red
                    'Today.TButton': '#E91E63',         # Hot Pink
                    'ImportantEvent.TButton': '#FF5722', # Bright Orange
                    'Draft.TButton': '#7B1FA2',         # Deep Purple
                    'FreeAgency.TButton': '#388E3C',    # Forest Green
                    'Menu.TButton': self.parent.CONTENT_BG  # Default
                }
                
                # Use tk.Button for more reliable color display
                button_bg = color_map.get(button_style, self.parent.CONTENT_BG)
                button_fg = 'white' if button_style != 'AllStar.TButton' else 'black'
                
                if button_style == 'Menu.TButton':
                    button_fg = self.parent.TEXT_COLOR
                
                btn = tk.Button(self.calendar_frame, text=button_text, 
                              bg=button_bg, fg=button_fg,
                              font=(self.parent.FONT_FAMILY, 8, 'bold' if 'Game' in button_style or 'Star' in button_style else 'normal'),
                              relief='raised', borderwidth=1,
                              command=lambda d=button_date: self._select_date(d))
                btn.grid(row=week_num, column=day_num, padx=1, pady=1, sticky='nsew')
                
                self.day_buttons[button_date] = btn
                
    def _select_date(self, selected_date):
        """Handle date selection."""
        self.selected_date = selected_date
        self._update_details_panel()
        
    def _update_details_panel(self):
        """Update the details panel with selected date information."""
        if not self.selected_date:
            return
            
        # Update selected date label
        date_str = self.selected_date.strftime("%A, %B %d, %Y")
        self.selected_date_label.config(text=date_str)
        
        # Clear and populate events
        self.events_text.delete(1.0, tk.END)
        
        events = self.events_by_date.get(self.selected_date, [])
        
        # Check if this date has trade deadline events
        has_trade_deadline = any(event.get('type') == 'trade_deadline' for event in events)
        
        if not events:
            self.events_text.insert(tk.END, "No events scheduled for this date.")
        else:
            for i, event in enumerate(events):
                if i > 0:
                    self.events_text.insert(tk.END, "\n" + "─" * 40 + "\n\n")
                    
                # Event title
                self.events_text.insert(tk.END, f"{event['title']}\n", 'title')
                
                # Event description
                self.events_text.insert(tk.END, f"{event['description']}\n\n")
                
                # Additional details for games
                if event['type'] == 'game':
                    location = "Home Ice" if event['is_home'] else f"{event['opponent'].city}"
                    self.events_text.insert(tk.END, f"Location: {location}\n")
                    self.events_text.insert(tk.END, f"Opponent: {event['opponent'].team_name}\n")
                    
                    # Check if game has been played
                    game_result = self._get_game_result(self.selected_date, event['opponent'])
                    if game_result:
                        self.events_text.insert(tk.END, f"Result: {game_result}\n")
        
        # Configure text tags
        self.events_text.tag_configure('title', font=(self.parent.FONT_FAMILY, 12, 'bold'))
        
        # Update action buttons based on the selected date
        if has_trade_deadline:
            self._create_trade_deadline_actions()
        else:
            self._create_default_actions()
        
    def _get_game_result(self, game_date, opponent):
        """Get the result of a game if it has been played."""
        for result in self.parent.game_results:
            if (result['date'] == game_date and 
                opponent in (result['home_team'], result['away_team'])):
                
                if self.parent.user_team == result['home_team']:
                    user_score = result['home_score']
                    opp_score = result['away_score']
                else:
                    user_score = result['away_score']
                    opp_score = result['home_score']
                
                result_text = "Won" if result['winner'] == self.parent.user_team else "Lost"
                return f"{result_text} {user_score}-{opp_score}"
        return None
        
    def _prev_month(self):
        """Navigate to previous month."""
        if self.current_view_date.month == 1:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year - 1, month=12)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month - 1)
        self._populate_calendar()
        
    def _next_month(self):
        """Navigate to next month."""
        if self.current_view_date.month == 12:
            self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year + 1, month=1)
        else:
            self.current_view_date = self.current_view_date.replace(month=self.current_view_date.month + 1)
        self._populate_calendar()
        
    def _go_to_today(self):
        """Navigate to current date."""
        self.current_view_date = self.parent.current_date
        self._populate_calendar()
        self._select_date(self.parent.current_date)
        
    def _view_game_details(self):
        """View detailed game information."""
        if not self.selected_date:
            return
            
        events = self.events_by_date.get(self.selected_date, [])
        game_events = [e for e in events if e['type'] == 'game']
        
        if game_events:
            # Open game details or schedule window
            self.parent.open_schedule_window()
            
    def _view_team_stats(self):
        """View team statistics."""
        self.parent.open_roster_window()
        
    def _view_news(self):
        """View news and updates."""
        self.parent.open_news_window()
        
    def update_calendar(self):
        """Refresh the calendar with current data."""
        self._load_season_events()
        self._populate_calendar()
        if self.selected_date:
            self._update_details_panel()
    
    def update_views(self):
        """Refresh the calendar - called by main window when sim advances.
        
        This is the standard interface that main.py's _update_heavy_panels
        looks for on all open windows.
        """
        try:
            # Only refresh if window still exists
            if self.winfo_exists():
                self.update_calendar()
        except tk.TclError:
            # Window was destroyed, ignore
            pass