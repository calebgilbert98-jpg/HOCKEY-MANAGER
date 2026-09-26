"""
Trade Deadline Center - Immersive Trade Deadline Day Experience
Accessible only on March 8th (NHL Trade Deadline Day)
"""

import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime, timedelta
import threading
import random

# Import the trade deadline manager for backend logic
from trade_deadline_manager import TradeDeadlineManager, get_deadline_manager


class TradeDeadlineCenter(tk.Toplevel):
    """Immersive Trade Deadline Center - Active only on Trade Deadline Day"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # Initialize trade deadline manager
        self.deadline_manager = get_deadline_manager(getattr(parent, 'game_manager', None))
        
        # Deadline Constants (from manager)
        self.DEADLINE_HOUR = self.deadline_manager.DEADLINE_HOUR
        self.DEADLINE_MINUTE = self.deadline_manager.DEADLINE_MINUTE
        
        # Animated Elements Control
        self.ticker_position = 0
        self.countdown_flash = False
        self.deadline_passed = False
        self.auto_trades_active = True
        
        # Trade Activity Data (now managed by deadline_manager)
        self.recent_trades = []
        self.trade_rumors = [
            "Sources: Maple Leafs exploring rental options",
            "Bruins actively shopping veteran defenseman", 
            "Rangers looking to add scoring depth",
            "Lightning cap situation limiting deadline moves",
            "Avalanche targeting goaltender depth",
            "Oilers seeking defensive upgrade before deadline"
        ]
        
        # Notification system for breaking news
        self.news_queue = []
        self.notification_active = False
        
        self._setup_window()
        self._create_styles()
        self._create_interface()
        self._start_animations()
        
        # Check for breaking news every 30 seconds
        self._check_breaking_news()
        
    def _setup_window(self):
        """Configure the main window with immersive design"""
        self.title("NHL TRADE DEADLINE CENTER")
        self.configure(bg='#0D1421')  # Deep navy background
        try:
            self.state('zoomed')  # Full screen on Windows
        except Exception:
            self.geometry("1600x950")  # Fallback for Linux/macOS
        
        # Window styling
        self.attributes('-topmost', True)
        self.protocol("WM_DELETE_WINDOW", self._close_deadline_center)
        
    def _close_deadline_center(self):
        """Close the trade deadline center"""
        self.auto_trades_active = False
        self.destroy()

    def _create_intelligence_panel(self, parent):
        """Right column: league intelligence - rumors and buyers/sellers"""
        panel = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        panel.pack(side='right', fill='both', expand=True, padx=(10, 0))

        tk.Label(panel, text="LEAGUE INTELLIGENCE", bg=self.PANEL_COLOR,
                 fg=self.DEADLINE_GOLD, font=('Segoe UI', 13, 'bold')).pack(pady=(10, 6))

        tk.Label(panel, text="Latest Rumors", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=12)
        rumors_box = tk.Text(panel, bg=self.DEADLINE_BG, fg=self.TEXT_WHITE, height=9,
                             font=('Segoe UI', 10), wrap='word', relief='flat',
                             highlightthickness=0)
        rumors_box.pack(fill='x', padx=12, pady=(4, 10))
        for rumor in getattr(self, 'trade_rumors', []):
            rumors_box.insert('end', f"\u2022 {rumor}\n\n")
        rumors_box.config(state='disabled')

        tk.Label(panel, text="Buyers / Sellers Watch", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=12)
        intel_box = tk.Text(panel, bg=self.DEADLINE_BG, fg=self.TEXT_WHITE, height=9,
                            font=('Segoe UI', 10), wrap='word', relief='flat',
                            highlightthickness=0)
        intel_box.pack(fill='both', expand=True, padx=12, pady=(4, 12))
        try:
            activity = self.deadline_manager.get_team_activity_status()
            buyers = [t for t, a in activity.items() if a.get('activity_level') == 'hot'][:6]
            sellers = [t for t, a in activity.items() if a.get('activity_level') == 'warm'][:6]
            intel_box.insert('end', "BUYERS:\n" + ("\n".join(f"  \u25b2 {t}" for t in buyers) or "  --") + "\n\n")
            intel_box.insert('end', "SELLERS:\n" + ("\n".join(f"  \u25bc {t}" for t in sellers) or "  --"))
        except Exception:
            intel_box.insert('end', "Intel unavailable.")
        intel_box.config(state='disabled')

    def _create_footer(self, parent):
        """Footer with deadline status and close button"""
        footer = tk.Frame(parent, bg=self.DEADLINE_BG)
        footer.pack(fill='x', pady=(15, 0))
        self.status_label = tk.Label(footer, text="Trade deadline is today - all deals must be finalized before the cutoff.",
                                     bg=self.DEADLINE_BG, fg=self.DEADLINE_GOLD,
                                     font=('Segoe UI', 11))
        self.status_label.pack(side='left')
        tk.Button(footer, text="Close Center", bg=self.NEUTRAL_GRAY, fg=self.TEXT_WHITE,
                  font=('Segoe UI', 11, 'bold'), relief='flat', padx=16, pady=6,
                  command=self._close_deadline_center).pack(side='right')

    def _start_animations(self):
        """Start countdown and ticker animations"""
        self._update_countdown()
        self._animate_ticker()

    def _update_countdown(self):
        """Update the countdown timer each second"""
        if getattr(self, 'deadline_passed', False):
            return
        try:
            time_info = self.deadline_manager.get_time_until_deadline()
            if time_info.get('expired'):
                self.deadline_passed = True
                self.countdown_label.config(text="DEADLINE PASSED", foreground=self.NEUTRAL_GRAY)
                self.status_label.config(text="TRADE DEADLINE HAS PASSED - No more trades allowed")
                return
            self.countdown_label.config(text=time_info.get('formatted', '--:--:--'))
        except Exception:
            pass
        if self.winfo_exists():
            self.after(1000, self._update_countdown)

    def _animate_ticker(self):
        """Scroll the news ticker"""
        try:
            x = self.ticker_label.winfo_x() - 2
            if x < -self.ticker_label.winfo_width():
                x = self.ticker_label.master.winfo_width()
            self.ticker_label.place(x=x, y=10)
        except Exception:
            pass
        if self.winfo_exists():
            self.after(50, self._animate_ticker)

    def _create_styles(self):
        """Create custom styles for deadline center"""
        style = ttk.Style()
        
        # Deadline theme colors
        self.DEADLINE_BG = '#0D1421'      # Deep navy
        self.URGENT_RED = '#FF1744'       # Bright red for urgency
        self.DEADLINE_RED = '#FF1744'     # Alias for urgency red
        self.DEADLINE_GOLD = '#FFD600'    # Gold for highlights
        self.NEUTRAL_GRAY = '#37474F'     # Gray for inactive elements
        self.TEXT_WHITE = '#FFFFFF'       # White text
        self.SUCCESS_GREEN = '#00E676'    # Green for completed trades
        self.PANEL_COLOR = '#16202F'      # Panel background
        self.BORDER_COLOR = '#2A3A52'     # Borders
        
        # Custom styles
        style.configure('Deadline.TFrame', background=self.DEADLINE_BG)
        style.configure('DeadlineTitle.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.URGENT_RED, 
                       font=('Segoe UI', 28, 'bold'))
        style.configure('DeadlineSubtitle.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.TEXT_WHITE, 
                       font=('Segoe UI', 16))
        style.configure('CountdownLabel.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.DEADLINE_GOLD, 
                       font=('Consolas', 48, 'bold'))
        style.configure('TickerLabel.TLabel', 
                       background=self.URGENT_RED, 
                       foreground=self.TEXT_WHITE, 
                       font=('Segoe UI', 12, 'bold'))
        style.configure('TradeButton.TButton', 
                       background=self.URGENT_RED,
                       foreground=self.TEXT_WHITE,
                       font=('Segoe UI', 12, 'bold'),
                       focuscolor='none')
        
    def _create_interface(self):
        """Create the main trade deadline interface"""
        # Main container
        main_frame = ttk.Frame(self, style='Deadline.TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header with title and countdown
        self._create_header(main_frame)
        
        # Breaking news ticker
        self._create_news_ticker(main_frame)
        
        # Main content area (3 columns)
        content_frame = ttk.Frame(main_frame, style='Deadline.TFrame')
        content_frame.pack(fill='both', expand=True, pady=(20, 0))
        
        # Left column - Market Activity
        self._create_market_activity_panel(content_frame)
        
        # Center column - Trade Tools
        self._create_trade_tools_panel(content_frame)
        
        # Right column - Intelligence & Rumors
        self._create_intelligence_panel(content_frame)
        
        # Footer with deadline status
        self._create_footer(main_frame)
        
    def _create_header(self, parent):
        """Create header with title and countdown"""
        header_frame = ttk.Frame(parent, style='Deadline.TFrame')
        header_frame.pack(fill='x', pady=(0, 20))
        
        # Title
        title_label = ttk.Label(header_frame, 
                               text="NHL TRADE DEADLINE CENTER", 
                               style='DeadlineTitle.TLabel')
        title_label.pack(pady=(0, 10))
        
        # Countdown timer
        countdown_frame = ttk.Frame(header_frame, style='Deadline.TFrame')
        countdown_frame.pack()
        
        ttk.Label(countdown_frame, 
                 text="TIME UNTIL DEADLINE:", 
                 style='DeadlineSubtitle.TLabel').pack()
        
        self.countdown_label = ttk.Label(countdown_frame, 
                                        text="--:--:--", 
                                        style='CountdownLabel.TLabel')
        self.countdown_label.pack()
        
    def _create_news_ticker(self, parent):
        """Create scrolling news ticker"""
        ticker_frame = ttk.Frame(parent, style='Deadline.TFrame')
        ticker_frame.pack(fill='x', pady=(0, 20))
        
        # Ticker background
        ticker_bg = tk.Frame(ticker_frame, bg=self.URGENT_RED, height=40)
        ticker_bg.pack(fill='x')
        ticker_bg.pack_propagate(False)
        
        # Scrolling label
        self.ticker_label = tk.Label(ticker_bg, 
                                    text="BREAKING: Multiple teams active in trade discussions... Stay tuned for updates!", 
                                    bg=self.URGENT_RED, 
                                    fg=self.TEXT_WHITE, 
                                    font=('Segoe UI', 12, 'bold'))
        self.ticker_label.place(x=0, y=10)
        
    def _create_market_activity_panel(self, parent):
        """Create left panel showing market activity"""
        # Left column
        left_frame = ttk.Frame(parent, style='Deadline.TFrame')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Market Activity Header
        market_header = ttk.Label(left_frame, 
                                 text="MARKET ACTIVITY", 
                                 style='DeadlineSubtitle.TLabel')
        market_header.pack(pady=(0, 15))
        
        # Team Activity Grid
        activity_frame = tk.Frame(left_frame, bg=self.DEADLINE_BG)
        activity_frame.pack(fill='both', expand=True)
        
        # Create team activity indicators
        self._create_team_activity_grid(activity_frame)
        
    def _create_team_activity_grid(self, parent):
        """Create grid showing team trading activity using real market data"""
        # Get real team activity from deadline manager
        team_activity = self.deadline_manager.get_team_activity_status()
        
        # Convert to list for grid display (first 12 teams)
        teams_to_show = list(team_activity.items())[:12]
        
        row = 0
        for i, (team, activity) in enumerate(teams_to_show):
            if i % 4 == 0:  # New row every 4 teams
                row += 1
            
            col = i % 4
            
            # Team frame with activity-based coloring
            bg_color = self.NEUTRAL_GRAY
            if activity['activity_level'] == 'hot':
                bg_color = '#CC1B00'  # Red-ish for hot
            elif activity['activity_level'] == 'warm':
                bg_color = '#FF6F00'  # Orange for warm
            
            team_frame = tk.Frame(parent, bg=bg_color, relief='raised', bd=2)
            team_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            
            # Team info with real data
            tk.Label(team_frame, text=team, bg=bg_color, fg=self.TEXT_WHITE, 
                    font=('Segoe UI', 10, 'bold')).pack()
            tk.Label(team_frame, text=activity['indicator'], bg=bg_color, 
                    font=('Segoe UI', 16)).pack()
            tk.Label(team_frame, text=activity['status_text'], bg=bg_color, fg=self.DEADLINE_GOLD, 
                    font=('Segoe UI', 8)).pack()
        
        # Configure grid weights
        for i in range(4):
            parent.grid_columnconfigure(i, weight=1)
        
    def _create_trade_tools_panel(self, parent):
        """Create center panel with trade tools"""
        # Center column
        center_frame = ttk.Frame(parent, style='Deadline.TFrame')
        center_frame.pack(side='left', fill='both', expand=True, padx=(10, 10))
        
        # Trade Tools Header
        tools_header = ttk.Label(center_frame, 
                                text="DEADLINE TOOLS", 
                                style='DeadlineSubtitle.TLabel')
        tools_header.pack(pady=(0, 15))
        
        # Quick action buttons
        self._create_quick_actions(center_frame)
        
        # Recent trades list
        self._create_recent_trades_list(center_frame)
        
        # Player movement tracker
        self._create_player_movement_tracker(center_frame)
        
    def _create_quick_actions(self, parent):
        """Create quick action buttons for deadline day"""
        actions_frame = ttk.Frame(parent, style='Deadline.TFrame')
        actions_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(actions_frame, 
                 text="DEADLINE ACTIONS", 
                 style='DeadlineSubtitle.TLabel').pack(pady=(0, 10))
        
        buttons_frame = tk.Frame(actions_frame, bg=self.PANEL_COLOR)
        buttons_frame.pack(fill='x')
        
        # Quick Trade Proposal button
        quick_trade_btn = tk.Button(
            buttons_frame,
            text="� QUICK TRADE",
            command=self._open_quick_trade_interface,
            bg=self.URGENT_RED,
            fg=self.TEXT_WHITE,
            font=('Segoe UI', 10, 'bold'),
            relief='raised',
            bd=3,
            padx=20,
            pady=8
        )
        quick_trade_btn.pack(side='left', padx=5)
        
        # Emergency Trade button
        emergency_btn = tk.Button(
            buttons_frame,
            text="EMERGENCY TRADE",
            command=self._open_emergency_trade,
            bg=self.DEADLINE_RED,
            fg=self.TEXT_WHITE,
            font=('Segoe UI', 10, 'bold'),
            relief='raised',
            bd=3,
            padx=20,
            pady=8
        )
        emergency_btn.pack(side='left', padx=5)
        
        # Market Browser button
        market_btn = tk.Button(
            buttons_frame,
            text="� BROWSE MARKET",
            command=self._open_market_browser,
            bg=self.DEADLINE_GOLD,
            fg='black',
            font=('Segoe UI', 10, 'bold'),
            relief='raised',
            bd=3,
            padx=20,
            pady=8
        )
        market_btn.pack(side='left', padx=5)
        
        # Deadline Status indicator
        self._create_deadline_status_indicator(buttons_frame)
        
    def _create_recent_trades_list(self, parent):
        """Create list of recent trades with enhanced display"""
        trades_frame = ttk.Frame(parent, style='Deadline.TFrame')
        trades_frame.pack(fill='both', expand=True)
        
        ttk.Label(trades_frame, 
                 text="RECENT TRADES", 
                 style='DeadlineSubtitle.TLabel').pack(pady=(0, 10))
        
        # Create scrollable frame for trades
        trades_canvas = tk.Canvas(trades_frame, bg=self.NEUTRAL_GRAY, height=200)
        trades_scrollbar = ttk.Scrollbar(trades_frame, orient="vertical", command=trades_canvas.yview)
        self.trades_scrollable_frame = ttk.Frame(trades_canvas, style='Deadline.TFrame')
        
        self.trades_scrollable_frame.bind(
            "<Configure>",
            lambda e: trades_canvas.configure(scrollregion=trades_canvas.bbox("all"))
        )
        
        trades_canvas.create_window((0, 0), window=self.trades_scrollable_frame, anchor="nw")
        trades_canvas.configure(yscrollcommand=trades_scrollbar.set)
        
        trades_canvas.pack(side="left", fill="both", expand=True)
        trades_scrollbar.pack(side="right", fill="y")
        
        # Initialize with sample trades (will be replaced with real data)
        self._populate_recent_trades()
        
        # Auto-refresh trades every 10 seconds
        self._schedule_trades_refresh()
        
    def _populate_recent_trades(self):
        """Populate the recent trades list with current data"""
        # Clear existing trades
        for widget in self.trades_scrollable_frame.winfo_children():
            widget.destroy()
        
        # Get recent trade activity from deadline manager
        recent_activity = self.deadline_manager.trade_activity_log[-15:]  # Last 15 trades
        
        if not recent_activity:
            # Show sample trades if no real activity
            sample_trades = [
                {
                    'timestamp': datetime.now() - timedelta(minutes=5),
                    'description': 'TOR acquires rental forward from ARI for 2nd round pick',
                    'impact': 'medium',
                    'teams_involved': ['TOR', 'ARI'],
                    'type': 'rental'
                },
                {
                    'timestamp': datetime.now() - timedelta(minutes=12),
                    'description': 'BOS trades veteran defenseman to VGK for prospect + pick',
                    'impact': 'high', 
                    'teams_involved': ['BOS', 'VGK'],
                    'type': 'futures'
                },
                {
                    'timestamp': datetime.now() - timedelta(minutes=18),
                    'description': 'NYR adds depth forward from MTL',
                    'impact': 'low',
                    'teams_involved': ['NYR', 'MTL'], 
                    'type': 'depth'
                }
            ]
            
            # Use generated activity from deadline manager
            generated_activity = self.deadline_manager.generate_trade_activity()
            if generated_activity:
                recent_activity = generated_activity
            else:
                recent_activity = sample_trades
        
        # Display each trade
        for i, trade in enumerate(recent_activity):
            self._create_trade_item(self.trades_scrollable_frame, trade, i)
            
    def _create_trade_item(self, parent, trade_data, index):
        """Create a single trade item display"""
        # Trade item frame
        trade_frame = tk.Frame(parent, bg=self.NEUTRAL_GRAY, relief='ridge', bd=1)
        trade_frame.pack(fill='x', padx=5, pady=2)
        
        # Time and impact indicator
        time_frame = tk.Frame(trade_frame, bg=self.NEUTRAL_GRAY)
        time_frame.pack(fill='x', padx=5, pady=2)
        
        # Timestamp
        if 'timestamp' in trade_data:
            time_str = trade_data['timestamp'].strftime("%H:%M")
        else:
            time_str = datetime.now().strftime("%H:%M")
            
        tk.Label(time_frame, text=time_str, bg=self.NEUTRAL_GRAY, fg=self.DEADLINE_GOLD,
                font=('Consolas', 9, 'bold')).pack(side='left')
        
        # Impact indicator
        impact = trade_data.get('impact', 'medium')
        impact_colors = {
            'low': '#4CAF50',      # Green
            'medium': '#FF9800',   # Orange  
            'high': '#F44336',     # Red
            'huge': '#9C27B0'      # Purple
        }
        
        impact_color = impact_colors.get(impact, '#FF9800')
        tk.Label(time_frame, text=f"●", bg=self.NEUTRAL_GRAY, fg=impact_color,
                font=('Segoe UI', 12)).pack(side='right')
        tk.Label(time_frame, text=impact.upper(), bg=self.NEUTRAL_GRAY, fg=impact_color,
                font=('Segoe UI', 8, 'bold')).pack(side='right', padx=(0, 5))
        
        # Trade description
        description = trade_data.get('description', 'Trade completed')
        desc_label = tk.Label(trade_frame, text=description, bg=self.NEUTRAL_GRAY, 
                             fg=self.TEXT_WHITE, font=('Segoe UI', 9),
                             wraplength=280, justify='left')
        desc_label.pack(fill='x', padx=5, pady=(0, 2))
        
        # Teams involved (if available)
        if 'teams_involved' in trade_data and trade_data['teams_involved']:
            teams_str = " ↔ ".join(trade_data['teams_involved'])
            tk.Label(trade_frame, text=teams_str, bg=self.NEUTRAL_GRAY, 
                    fg=self.DEADLINE_GOLD, font=('Segoe UI', 8, 'bold')).pack(pady=(0, 2))
    
    def _schedule_trades_refresh(self):
        """Schedule automatic refresh of trades list"""
        self._populate_recent_trades()
        
        # Schedule next refresh based on deadline urgency
        time_info = self.deadline_manager.get_time_until_deadline()
        if time_info['urgency'] == 'critical':
            refresh_interval = 5000  # 5 seconds when critical
        elif time_info['urgency'] == 'high':
            refresh_interval = 15000  # 15 seconds when high urgency
        else:
            refresh_interval = 30000  # 30 seconds normally
            
        self.after(refresh_interval, self._schedule_trades_refresh)
    
    def _check_breaking_news(self):
        """Check for breaking news and major trades"""
        # Get latest activity from deadline manager
        latest_activity = self.deadline_manager.get_breaking_news()
        
        if latest_activity:
            self.news_queue.extend(latest_activity)
            
        # Process news queue
        if self.news_queue and not self.notification_active:
            self._show_breaking_news()
            
        # Schedule next check
        self.after(30000, self._check_breaking_news)  # Every 30 seconds
        
    def _show_breaking_news(self):
        """Display breaking news banner"""
        if not self.news_queue:
            return
            
        news_item = self.news_queue.pop(0)
        self.notification_active = True
        
        # Create breaking news overlay
        news_overlay = tk.Frame(self, bg='#DC2626', relief='raised', bd=3)
        news_overlay.place(relx=0.5, rely=0.1, anchor='center', 
                          relwidth=0.8, height=60)
        
        # Breaking news label
        breaking_label = tk.Label(news_overlay, text="BREAKING NEWS",
                                 bg='#DC2626', fg='white',
                                 font=('Segoe UI', 12, 'bold'))
        breaking_label.pack(pady=2)
        
        # News content
        news_label = tk.Label(news_overlay, text=news_item,
                             bg='#DC2626', fg='white',
                             font=('Segoe UI', 10),
                             wraplength=600)
        news_label.pack(pady=2)
        
        # Auto-dismiss after 8 seconds
        def dismiss_news():
            news_overlay.destroy()
            self.notification_active = False
            
        self.after(8000, dismiss_news)
        
        # Flash effect
        def flash_news():
            current_bg = news_overlay.cget('bg')
            new_bg = '#EF4444' if current_bg == '#DC2626' else '#DC2626'
            news_overlay.configure(bg=new_bg)
            breaking_label.configure(bg=new_bg)
            news_label.configure(bg=new_bg)
            
        # Flash 3 times
        for i in range(6):  # 3 complete flash cycles
            self.after(i * 200, flash_news)
    
    def _create_player_movement_tracker(self, parent):
        """Create player movement and impact tracker"""
        movement_frame = ttk.Frame(parent, style='Deadline.TFrame')
        movement_frame.pack(fill='both', expand=True, pady=(20, 0))
        
        ttk.Label(movement_frame, 
                 text="PLAYER MOVEMENT TRACKER", 
                 style='DeadlineSubtitle.TLabel').pack(pady=(0, 10))
        
        # Stats frame
        stats_frame = tk.Frame(movement_frame, bg=self.PANEL_COLOR)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        # Today's movement stats
        self._create_movement_stats(stats_frame)
        
        # Impact players on the move
        impact_frame = tk.Frame(movement_frame, bg=self.PANEL_COLOR, relief='sunken', bd=2)
        impact_frame.pack(fill='both', expand=True)
        
        ttk.Label(impact_frame, text="Impact Players Available",
                 background=self.PANEL_COLOR, foreground=self.DEADLINE_GOLD,
                 font=('Segoe UI', 10, 'bold')).pack(pady=5)
        
        # Available impact players list
        self._create_impact_players_list(impact_frame)
        
    def _create_movement_stats(self, parent):
        """Create movement statistics display"""
        stats_container = tk.Frame(parent, bg=self.PANEL_COLOR)
        stats_container.pack(fill='x', padx=5, pady=5)
        
        # Get movement data from deadline manager
        deadline_summary = self.deadline_manager.get_deadline_summary()
        stats = deadline_summary.get('statistics', {})
        
        # Movement metrics
        movements_today = stats.get('players_moved', random.randint(8, 25))
        trades_today = stats.get('total_trades', random.randint(3, 12))
        biggest_deal = stats.get('biggest_deal_value', random.randint(2, 8))
        
        metrics = [
            ("Players Moved Today", str(movements_today), self.SUCCESS_GREEN),
            ("Trades Completed", str(trades_today), self.DEADLINE_GOLD),
            ("Biggest Deal Value", f"${biggest_deal}M", self.URGENT_RED)
        ]
        
        for i, (label, value, color) in enumerate(metrics):
            metric_frame = tk.Frame(stats_container, bg=self.PANEL_COLOR)
            metric_frame.pack(side='left' if i < 2 else 'right', fill='x', expand=True, padx=5)
            
            tk.Label(metric_frame, text=value, bg=self.PANEL_COLOR, fg=color,
                    font=('Segoe UI', 14, 'bold')).pack()
            tk.Label(metric_frame, text=label, bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 8)).pack()
    
    def _create_impact_players_list(self, parent):
        """Create list of high-impact players potentially available"""
        players_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        players_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Sample impact players (in real game, this would come from actual data)
        impact_players = [
            {"name": "Jake Guentzel", "pos": "LW", "team": "PIT", "status": "Rumored", "value": "High"},
            {"name": "Noah Hanifin", "pos": "D", "team": "CGY", "status": "Available", "value": "High"},
            {"name": "Chris Tanev", "pos": "D", "team": "CGY", "status": "Likely", "value": "Medium"},
            {"name": "Anthony Duclair", "pos": "RW", "team": "SJS", "status": "Available", "value": "Medium"},
            {"name": "Tyler Toffoli", "pos": "RW", "team": "NJD", "status": "Possible", "value": "Medium"}
        ]
        
        # Headers
        headers_frame = tk.Frame(players_frame, bg=self.NEUTRAL_GRAY)
        headers_frame.pack(fill='x', pady=(0, 2))
        
        headers = ["Player", "Pos", "Team", "Status", "Value"]
        widths = [120, 40, 50, 80, 60]
        
        for header, width in zip(headers, widths):
            tk.Label(headers_frame, text=header, bg=self.NEUTRAL_GRAY, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 9, 'bold'), width=width//8).pack(side='left', padx=2)
        
        # Player rows
        for player in impact_players:
            player_frame = tk.Frame(players_frame, bg=self.PANEL_COLOR)
            player_frame.pack(fill='x', pady=1)
            
            # Status color coding
            status_colors = {
                'Available': self.SUCCESS_GREEN,
                'Rumored': self.DEADLINE_GOLD,
                'Likely': self.URGENT_RED,
                'Possible': '#9CA3AF'
            }
            
            value_colors = {
                'High': self.URGENT_RED,
                'Medium': self.DEADLINE_GOLD,
                'Low': self.SUCCESS_GREEN
            }
            
            # Player data
            values = [
                (player['name'], self.TEXT_WHITE),
                (player['pos'], self.TEXT_WHITE),
                (player['team'], self.DEADLINE_GOLD),
                (player['status'], status_colors.get(player['status'], self.TEXT_WHITE)),
                (player['value'], value_colors.get(player['value'], self.TEXT_WHITE))
            ]
            
            for (value, color), width in zip(values, widths):
                tk.Label(player_frame, text=value, bg=self.PANEL_COLOR, fg=color,
                        font=('Segoe UI', 9), width=width//8).pack(side='left', padx=2)
    
    def _create_deadline_status_indicator(self, parent):
        """Create deadline status indicator"""
        status_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        status_frame.pack(side='right', padx=10)
        
        time_info = self.deadline_manager.get_time_until_deadline()
        
        if time_info['urgency'] == 'critical':
            status_color = self.URGENT_RED
            status_text = "CRITICAL"
        elif time_info['urgency'] == 'high':
            status_color = self.DEADLINE_GOLD
            status_text = "HIGH"
        else:
            status_color = self.SUCCESS_GREEN
            status_text = "NORMAL"
            
        tk.Label(status_frame, text="Market Status:", bg=self.PANEL_COLOR, 
                fg=self.TEXT_WHITE, font=('Segoe UI', 9)).pack()
        tk.Label(status_frame, text=status_text, bg=self.PANEL_COLOR,
                fg=status_color, font=('Segoe UI', 10, 'bold')).pack()
    
    def _open_quick_trade_interface(self):
        """Open the quick trade proposal interface"""
        QuickTradeInterface(self, self.deadline_manager)
    
    def _open_emergency_trade(self):
        """Open emergency trade interface for last-minute deals"""
        EmergencyTradeInterface(self, self.deadline_manager)
    
    def _open_market_browser(self):
        """Open comprehensive market browser"""
        DeadlineMarketBrowser(self, self.deadline_manager)


class QuickTradeInterface(tk.Toplevel):
    """Quick trade proposal interface for deadline day"""
    
    def __init__(self, parent, deadline_manager):
        super().__init__(parent)
        self.parent = parent
        self.deadline_manager = deadline_manager
        
        # Colors from parent
        self.BG_COLOR = parent.BG_COLOR
        self.PANEL_COLOR = parent.PANEL_COLOR
        self.TEXT_WHITE = parent.TEXT_WHITE
        self.DEADLINE_GOLD = parent.DEADLINE_GOLD
        self.URGENT_RED = parent.URGENT_RED
        
        self._setup_window()
        self._create_interface()
        
    def _setup_window(self):
        """Setup window properties"""
        self.title("Quick Trade Proposal - Trade Deadline")
        self.geometry("800x600")
        self.configure(bg=self.BG_COLOR)
        self.resizable(False, False)
        
        # Center on parent
        self.transient(self.parent)
        self.grab_set()
        
    def _create_interface(self):
        """Create the quick trade interface"""
        # Header
        header = tk.Frame(self, bg=self.URGENT_RED, height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        time_info = self.deadline_manager.get_time_until_deadline()
        tk.Label(header, text=f"QUICK TRADE - {time_info['formatted']} REMAINING",
                bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                font=('Segoe UI', 16, 'bold')).pack(expand=True)
        
        # Main content
        content = tk.Frame(self, bg=self.PANEL_COLOR)
        content.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Trading team selection
        self._create_team_selector(content)
        
        # Player selection areas
        self._create_player_selector(content)
        
        # Trade evaluation
        self._create_trade_evaluation(content)
        
        # Action buttons
        self._create_action_buttons(content)
    
    def _create_team_selector(self, parent):
        """Create team selection interface"""
        teams_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        teams_frame.pack(fill='x', pady=(0, 20))
        
        tk.Label(teams_frame, text="Select Trading Partner:",
                bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        
        # Quick team buttons (active teams on deadline day)
        active_teams = ['TOR', 'BOS', 'NYR', 'TBL', 'FLA', 'COL', 'EDM', 'VGK', 'DAL', 'CAR']
        buttons_frame = tk.Frame(teams_frame, bg=self.PANEL_COLOR)
        buttons_frame.pack(fill='x', pady=10)
        
        for i, team in enumerate(active_teams[:5]):
            btn = tk.Button(buttons_frame, text=team,
                          bg=self.DEADLINE_GOLD, fg='black',
                          font=('Segoe UI', 10, 'bold'),
                          width=8, command=lambda t=team: self._select_team(t))
            btn.pack(side='left', padx=5)
            
    def _create_player_selector(self, parent):
        """Create player selection interface"""
        players_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        players_frame.pack(fill='both', expand=True, pady=(0, 20))
        
        # Your offer side
        your_frame = tk.LabelFrame(players_frame, text="Your Offer", 
                                  bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                                  font=('Segoe UI', 11, 'bold'))
        your_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Quick player buttons for common trade pieces
        common_assets = ['1st Round Pick', '2nd Round Pick', 'Prospect', 'Rental Player', 'Cap Space']
        for asset in common_assets:
            btn = tk.Button(your_frame, text=f"+ {asset}",
                          bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                          font=('Segoe UI', 9), relief='ridge')
            btn.pack(fill='x', padx=5, pady=2)
        
        # Their offer side
        their_frame = tk.LabelFrame(players_frame, text="Their Offer",
                                   bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                                   font=('Segoe UI', 11, 'bold'))
        their_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Available players from selected team
        available_players = ['Impact Forward', 'Veteran Defenseman', 'Backup Goalie', 'Depth Player']
        for player in available_players:
            btn = tk.Button(their_frame, text=f"+ {player}",
                          bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                          font=('Segoe UI', 9), relief='ridge')
            btn.pack(fill='x', padx=5, pady=2)
    
    def _create_trade_evaluation(self, parent):
        """Create trade evaluation display"""
        eval_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='sunken', bd=2)
        eval_frame.pack(fill='x', pady=(0, 20))
        
        tk.Label(eval_frame, text="Trade Evaluation",
                bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 12, 'bold')).pack(pady=10)
        
        # Quick evaluation metrics
        metrics = [
            ("Trade Fairness", "Needs More Assets", self.URGENT_RED),
            ("Cap Impact", "Manageable", self.DEADLINE_GOLD),
            ("Deadline Value", "High", '#10B981')
        ]
        
        for metric, value, color in metrics:
            metric_frame = tk.Frame(eval_frame, bg=self.PANEL_COLOR)
            metric_frame.pack(fill='x', padx=20, pady=2)
            
            tk.Label(metric_frame, text=f"{metric}:", bg=self.PANEL_COLOR,
                    fg=self.TEXT_WHITE, font=('Segoe UI', 10)).pack(side='left')
            tk.Label(metric_frame, text=value, bg=self.PANEL_COLOR,
                    fg=color, font=('Segoe UI', 10, 'bold')).pack(side='right')
    
    def _create_action_buttons(self, parent):
        """Create action buttons"""
        buttons_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        buttons_frame.pack(fill='x')
        
        # Send Proposal button
        send_btn = tk.Button(buttons_frame, text="SEND PROPOSAL",
                            bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                            font=('Segoe UI', 12, 'bold'), padx=30, pady=10,
                            command=self._send_proposal)
        send_btn.pack(side='left', padx=(0, 10))
        
        # Cancel button
        cancel_btn = tk.Button(buttons_frame, text="CANCEL",
                              bg='#6B7280', fg=self.TEXT_WHITE,
                              font=('Segoe UI', 12, 'bold'), padx=30, pady=10,
                              command=self.destroy)
        cancel_btn.pack(side='right')
        
    def _select_team(self, team):
        """Handle team selection"""
        print(f"Selected team: {team}")
        
    def _send_proposal(self):
        """Send trade proposal"""
        print("Trade proposal sent!")
        self.destroy()


class EmergencyTradeInterface(tk.Toplevel):
    """Emergency trade interface for last-minute deadline deals"""
    
    def __init__(self, parent, deadline_manager):
        super().__init__(parent)
        self.parent = parent
        self.deadline_manager = deadline_manager
        
        # Colors from parent
        self.BG_COLOR = parent.BG_COLOR
        self.PANEL_COLOR = parent.PANEL_COLOR
        self.TEXT_WHITE = parent.TEXT_WHITE
        self.DEADLINE_RED = parent.DEADLINE_RED
        self.URGENT_RED = parent.URGENT_RED
        
        self._setup_window()
        self._create_interface()
        
    def _setup_window(self):
        """Setup emergency window"""
        self.title("EMERGENCY TRADE - DEADLINE IMMINENT")
        self.geometry("600x400")
        self.configure(bg=self.DEADLINE_RED)
        self.resizable(False, False)
        
        # Center and make urgent
        self.transient(self.parent)
        self.grab_set()
        self.attributes('-topmost', True)
        
    def _create_interface(self):
        """Create emergency interface"""
        # Flash warning
        warning_frame = tk.Frame(self, bg=self.URGENT_RED, height=80)
        warning_frame.pack(fill='x')
        warning_frame.pack_propagate(False)
        
        time_info = self.deadline_manager.get_time_until_deadline()
        tk.Label(warning_frame, text="EMERGENCY TRADE MODE",
                bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                font=('Segoe UI', 18, 'bold')).pack(expand=True)
        
        tk.Label(warning_frame, text=f"DEADLINE: {time_info['formatted']}",
                bg=self.URGENT_RED, fg='yellow',
                font=('Segoe UI', 12, 'bold')).pack()
        
        # Quick options
        content = tk.Frame(self, bg=self.PANEL_COLOR)
        content.pack(fill='both', expand=True, padx=20, pady=20)
        
        tk.Label(content, text="Emergency Options:",
                bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                font=('Segoe UI', 14, 'bold')).pack(pady=(0, 20))
        
        # Emergency trade options
        options = [
            ("Accept Any Reasonable Offer", "Auto-accept trades within 10% of fair value"),
            ("Fire Sale Mode", "Trade anyone not in core group"),
            ("Deadline Extension Request", "Request 5-minute emergency extension")
        ]
        
        for title, desc in options:
            option_frame = tk.Frame(content, bg=self.PANEL_COLOR, relief='ridge', bd=2)
            option_frame.pack(fill='x', pady=5)
            
            btn = tk.Button(option_frame, text=title,
                          bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                          font=('Segoe UI', 11, 'bold'),
                          command=lambda t=title: self._emergency_action(t))
            btn.pack(fill='x', padx=5, pady=5)
            
            tk.Label(option_frame, text=desc,
                    bg=self.PANEL_COLOR, fg='#9CA3AF',
                    font=('Segoe UI', 9)).pack(padx=5, pady=(0, 5))
        
    def _emergency_action(self, action):
        """Handle emergency action"""
        print(f"Emergency action: {action}")
        self.destroy()


class DeadlineMarketBrowser(tk.Toplevel):
    """Comprehensive market browser for deadline day trading"""
    
    def __init__(self, parent, deadline_manager):
        super().__init__(parent)
        self.parent = parent
        self.deadline_manager = deadline_manager
        
        # Colors from parent
        self.BG_COLOR = parent.BG_COLOR
        self.PANEL_COLOR = parent.PANEL_COLOR
        self.TEXT_WHITE = parent.TEXT_WHITE
        self.DEADLINE_GOLD = parent.DEADLINE_GOLD
        self.DEADLINE_RED = parent.DEADLINE_RED
        self.SUCCESS_GREEN = parent.SUCCESS_GREEN
        self.URGENT_RED = parent.URGENT_RED
        
        self._setup_window()
        self._create_interface()
        
    def _setup_window(self):
        """Setup market browser window"""
        self.title("Deadline Market Intelligence")
        self.geometry("1200x800")
        self.configure(bg=self.BG_COLOR)
        
        # Center on parent
        self.transient(self.parent)
        
    def _create_interface(self):
        """Create comprehensive market browser interface"""
        # Header with market status
        self._create_header()
        
        # Main content with tabs
        self._create_main_content()
        
        # Footer with actions
        self._create_footer()
        
    def _create_header(self):
        """Create header with market overview"""
        header_frame = tk.Frame(self, bg=self.DEADLINE_RED, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Title and time
        time_info = self.deadline_manager.get_time_until_deadline()
        
        title_frame = tk.Frame(header_frame, bg=self.DEADLINE_RED)
        title_frame.pack(expand=True, fill='both')
        
        tk.Label(title_frame, text="DEADLINE MARKET INTELLIGENCE",
                bg=self.DEADLINE_RED, fg=self.TEXT_WHITE,
                font=('Segoe UI', 18, 'bold')).pack(pady=5)
        
        tk.Label(title_frame, text=f"Market Analysis • {time_info['formatted']} to Deadline",
                bg=self.DEADLINE_RED, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 12)).pack()
        
    def _create_main_content(self):
        """Create main tabbed content area"""
        content_frame = tk.Frame(self, bg=self.BG_COLOR)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Create notebook for tabs
        from tkinter import ttk
        style = ttk.Style()
        style.configure('MarketBrowser.TNotebook', background=self.BG_COLOR)
        style.configure('MarketBrowser.TNotebook.Tab', 
                       background=self.PANEL_COLOR,
                       foreground=self.TEXT_WHITE,
                       font=('Segoe UI', 10, 'bold'))
        
        notebook = ttk.Notebook(content_frame, style='MarketBrowser.TNotebook')
        notebook.pack(fill='both', expand=True)
        
        # Market Overview Tab
        overview_tab = tk.Frame(notebook, bg=self.BG_COLOR)
        notebook.add(overview_tab, text='Market Overview')
        self._create_market_overview(overview_tab)
        
        # Buyers & Sellers Tab
        buyers_sellers_tab = tk.Frame(notebook, bg=self.BG_COLOR)
        notebook.add(buyers_sellers_tab, text='Buyers & Sellers')
        self._create_buyers_sellers(buyers_sellers_tab)
        
        # Position Analysis Tab
        position_tab = tk.Frame(notebook, bg=self.BG_COLOR)
        notebook.add(position_tab, text='Position Needs')
        self._create_position_analysis(position_tab)
        
        # Trade Predictions Tab
        predictions_tab = tk.Frame(notebook, bg=self.BG_COLOR)
        notebook.add(predictions_tab, text='Trade Predictions')
        self._create_trade_predictions(predictions_tab)
        
        # Salary Cap Tab
        cap_tab = tk.Frame(notebook, bg=self.BG_COLOR)
        notebook.add(cap_tab, text='Salary Cap Analysis')
        self._create_salary_cap_analysis(cap_tab)
        
    def _create_market_overview(self, parent):
        """Create market overview display"""
        # Market temperature gauge
        temp_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        temp_frame.pack(fill='x', pady=(0, 20))
        
        tk.Label(temp_frame, text="Market Temperature",
                bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        # Temperature display
        temp_info = self.deadline_manager.get_market_temperature()
        overall_temp = temp_info.get('overall', 'warm')
        
        temp_colors = {
            'cold': '#60A5FA',
            'warm': '#FBBF24', 
            'hot': '#F87171',
            'blazing': '#DC2626'
        }
        
        temp_color = temp_colors.get(overall_temp, '#FBBF24')
        
        tk.Label(temp_frame, text=overall_temp.upper(),
                bg=self.PANEL_COLOR, fg=temp_color,
                font=('Segoe UI', 24, 'bold')).pack()
        
        # Market statistics
        stats_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        stats_frame.pack(fill='both', expand=True)
        
        tk.Label(stats_frame, text="� Market Statistics",
                bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        # Get market intelligence
        market_intel = self.deadline_manager.get_market_intelligence()
        trends = market_intel.get('deadline_trends', {})
        
        # Statistics grid
        stats_grid = tk.Frame(stats_frame, bg=self.PANEL_COLOR)
        stats_grid.pack(fill='both', expand=True, padx=20, pady=10)
        
        stats = [
            ("Most Active Position", trends.get('most_active_position', 'Forwards')),
            ("Average Trade Size", f"{trends.get('average_trade_size', 2.3)} players"),
            ("Rental Market", f"{trends.get('rental_vs_futures', {}).get('rental', 65)}% rental"),
            ("Market Sentiment", trends.get('market_sentiment', 'Active'))
        ]
        
        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = i % 2
            
            stat_frame = tk.Frame(stats_grid, bg=self.PANEL_COLOR)
            stat_frame.grid(row=row, column=col, padx=20, pady=10, sticky='w')
            
            tk.Label(stat_frame, text=value,
                    bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 16, 'bold')).pack()
            
            tk.Label(stat_frame, text=label,
                    bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 10)).pack()
    
    def _create_buyers_sellers(self, parent):
        """Create buyers and sellers analysis"""
        # Split into buyers and sellers
        buyers_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        buyers_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        sellers_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        sellers_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Buyers section
        tk.Label(buyers_frame, text="ACTIVE BUYERS",
                bg=self.PANEL_COLOR, fg=self.SUCCESS_GREEN,
                font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        market_intel = self.deadline_manager.get_market_intelligence()
        buyers = market_intel.get('buyer_teams', [])
        
        buyers_list = tk.Frame(buyers_frame, bg=self.PANEL_COLOR)
        buyers_list.pack(fill='both', expand=True, padx=10, pady=10)
        
        for buyer in buyers[:6]:  # Show top 6 buyers
            buyer_item = tk.Frame(buyers_list, bg=self.BG_COLOR, relief='ridge', bd=1)
            buyer_item.pack(fill='x', pady=2)
            
            # Team name and likelihood
            header = tk.Frame(buyer_item, bg=self.BG_COLOR)
            header.pack(fill='x', padx=5, pady=2)
            
            tk.Label(header, text=buyer['team'],
                    bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 12, 'bold')).pack(side='left')
            
            likelihood_color = self.SUCCESS_GREEN if buyer['likelihood'] == 'High' else self.DEADLINE_GOLD
            tk.Label(header, text=buyer['likelihood'],
                    bg=self.BG_COLOR, fg=likelihood_color,
                    font=('Segoe UI', 10, 'bold')).pack(side='right')
            
            # Details
            details = f"Need: {buyer['primary_need']} | Cap: {buyer['cap_space']} | {buyer['assets']}"
            tk.Label(buyer_item, text=details,
                    bg=self.BG_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 9), wraplength=250).pack(padx=5, pady=2)
        
        # Sellers section
        tk.Label(sellers_frame, text="ACTIVE SELLERS",
                bg=self.PANEL_COLOR, fg=self.URGENT_RED,
                font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        sellers = market_intel.get('seller_teams', [])
        
        sellers_list = tk.Frame(sellers_frame, bg=self.PANEL_COLOR)
        sellers_list.pack(fill='both', expand=True, padx=10, pady=10)
        
        for seller in sellers[:6]:  # Show top 6 sellers
            seller_item = tk.Frame(sellers_list, bg=self.BG_COLOR, relief='ridge', bd=1)
            seller_item.pack(fill='x', pady=2)
            
            # Team name and likelihood
            header = tk.Frame(seller_item, bg=self.BG_COLOR)
            header.pack(fill='x', padx=5, pady=2)
            
            tk.Label(header, text=seller['team'],
                    bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 12, 'bold')).pack(side='left')
            
            likelihood_color = self.URGENT_RED if seller['likelihood'] == 'High' else self.DEADLINE_GOLD
            tk.Label(header, text=seller['likelihood'],
                    bg=self.BG_COLOR, fg=likelihood_color,
                    font=('Segoe UI', 10, 'bold')).pack(side='right')
            
            # Details
            details = f"Asset: {seller['notable_assets']} | Price: {seller['asking_price']}"
            tk.Label(seller_item, text=details,
                    bg=self.BG_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 9), wraplength=250).pack(padx=5, pady=2)
    
    def _create_position_analysis(self, parent):
        """Create position needs analysis"""
        tk.Label(parent, text="POSITION NEEDS ANALYSIS",
                bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 16, 'bold')).pack(pady=20)
        
        market_intel = self.deadline_manager.get_market_intelligence()
        position_needs = market_intel.get('position_needs', {})
        
        # Create position breakdown
        positions_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        positions_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        positions = [
            ('Forwards', position_needs.get('forwards', [])),
            ('Defensemen', position_needs.get('defensemen', [])),
            ('Goalies', position_needs.get('goalies', [])),
            ('Depth Players', position_needs.get('depth', []))
        ]
        
        for i, (pos_name, teams) in enumerate(positions):
            pos_frame = tk.Frame(positions_frame, bg=self.BG_COLOR, relief='raised', bd=2)
            pos_frame.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')
            
            tk.Label(pos_frame, text=pos_name,
                    bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 12, 'bold')).pack(pady=5)
            
            teams_text = ", ".join(teams) if teams else "No active needs"
            tk.Label(pos_frame, text=teams_text,
                    bg=self.BG_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 10), wraplength=200).pack(padx=10, pady=5)
        
        # Configure grid weights
        positions_frame.grid_columnconfigure(0, weight=1)
        positions_frame.grid_columnconfigure(1, weight=1)
    
    def _create_trade_predictions(self, parent):
        """Create trade predictions display"""
        tk.Label(parent, text="TRADE PREDICTIONS",
                bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 16, 'bold')).pack(pady=20)
        
        # Scrollable predictions list
        predictions_canvas = tk.Canvas(parent, bg=self.BG_COLOR)
        predictions_scrollbar = tk.Scrollbar(parent, orient="vertical", command=predictions_canvas.yview)
        predictions_frame = tk.Frame(predictions_canvas, bg=self.BG_COLOR)
        
        predictions_frame.bind(
            "<Configure>",
            lambda e: predictions_canvas.configure(scrollregion=predictions_canvas.bbox("all"))
        )
        
        predictions_canvas.create_window((0, 0), window=predictions_frame, anchor="nw")
        predictions_canvas.configure(yscrollcommand=predictions_scrollbar.set)
        
        predictions_canvas.pack(side="left", fill="both", expand=True, padx=20)
        predictions_scrollbar.pack(side="right", fill="y")
        
        # Get predictions
        market_intel = self.deadline_manager.get_market_intelligence()
        predictions = market_intel.get('trade_predictions', [])
        
        for prediction in predictions:
            pred_frame = tk.Frame(predictions_frame, bg=self.PANEL_COLOR, relief='raised', bd=2)
            pred_frame.pack(fill='x', padx=10, pady=5)
            
            # Likelihood bar
            likelihood = prediction['likelihood']
            likelihood_color = self.SUCCESS_GREEN if likelihood >= 70 else self.DEADLINE_GOLD if likelihood >= 50 else '#6B7280'
            
            header = tk.Frame(pred_frame, bg=self.PANEL_COLOR)
            header.pack(fill='x', padx=10, pady=5)
            
            tk.Label(header, text=f"{likelihood}% LIKELIHOOD",
                    bg=self.PANEL_COLOR, fg=likelihood_color,
                    font=('Segoe UI', 10, 'bold')).pack(side='left')
            
            teams_str = " ↔ ".join(prediction['teams_involved'])
            tk.Label(header, text=teams_str,
                    bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 10, 'bold')).pack(side='right')
            
            # Description
            tk.Label(pred_frame, text=prediction['description'],
                    bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 12, 'bold')).pack(padx=10, pady=2)
            
            # Details
            tk.Label(pred_frame, text=f"Assets: {prediction['assets']}",
                    bg=self.PANEL_COLOR, fg='#9CA3AF',
                    font=('Segoe UI', 10)).pack(padx=10)
            
            tk.Label(pred_frame, text=prediction['reasoning'],
                    bg=self.PANEL_COLOR, fg='#9CA3AF',
                    font=('Segoe UI', 9), wraplength=400).pack(padx=10, pady=(0, 5))
    
    def _create_salary_cap_analysis(self, parent):
        """Create salary cap analysis display"""
        tk.Label(parent, text="SALARY CAP ANALYSIS",
                bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                font=('Segoe UI', 16, 'bold')).pack(pady=20)
        
        # Cap analysis table
        cap_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        cap_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Headers
        headers_frame = tk.Frame(cap_frame, bg=self.BG_COLOR)
        headers_frame.pack(fill='x', pady=5)
        
        headers = ["Team", "Cap Space", "Deadline Space", "Flexibility", "Retention"]
        widths = [60, 100, 120, 100, 100]
        
        for header, width in zip(headers, widths):
            tk.Label(headers_frame, text=header, bg=self.BG_COLOR, fg=self.DEADLINE_GOLD,
                    font=('Segoe UI', 10, 'bold'), width=width//8).pack(side='left', padx=2)
        
        # Cap data
        market_intel = self.deadline_manager.get_market_intelligence()
        cap_analysis = market_intel.get('salary_cap_space', {})
        
        # Scrollable cap data
        cap_canvas = tk.Canvas(cap_frame, bg=self.PANEL_COLOR, height=400)
        cap_scrollbar = tk.Scrollbar(cap_frame, orient="vertical", command=cap_canvas.yview)
        cap_data_frame = tk.Frame(cap_canvas, bg=self.PANEL_COLOR)
        
        cap_data_frame.bind(
            "<Configure>",
            lambda e: cap_canvas.configure(scrollregion=cap_canvas.bbox("all"))
        )
        
        cap_canvas.create_window((0, 0), window=cap_data_frame, anchor="nw")
        cap_canvas.configure(yscrollcommand=cap_scrollbar.set)
        
        cap_canvas.pack(side="left", fill="both", expand=True)
        cap_scrollbar.pack(side="right", fill="y")
        
        for team, data in cap_analysis.items():
            row_frame = tk.Frame(cap_data_frame, bg=self.PANEL_COLOR)
            row_frame.pack(fill='x', pady=1)
            
            # Team
            tk.Label(row_frame, text=team, bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 9), width=widths[0]//8).pack(side='left', padx=2)
            
            # Cap space
            cap_space = data.get('cap_space', 0)
            cap_color = self.SUCCESS_GREEN if cap_space > 5000000 else self.DEADLINE_GOLD if cap_space > 1000000 else self.URGENT_RED
            tk.Label(row_frame, text=f"${cap_space//1000}K", bg=self.PANEL_COLOR, fg=cap_color,
                    font=('Segoe UI', 9), width=widths[1]//8).pack(side='left', padx=2)
            
            # Deadline space
            deadline_space = data.get('deadline_space', 0)
            tk.Label(row_frame, text=f"${deadline_space//1000}K", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 9), width=widths[2]//8).pack(side='left', padx=2)
            
            # Flexibility
            flexibility = data.get('flexibility', 'Medium')
            flex_color = self.SUCCESS_GREEN if flexibility == 'High' else self.DEADLINE_GOLD if flexibility == 'Medium' else self.URGENT_RED
            tk.Label(row_frame, text=flexibility, bg=self.PANEL_COLOR, fg=flex_color,
                    font=('Segoe UI', 9), width=widths[3]//8).pack(side='left', padx=2)
            
            # Retention slots
            retention = data.get('retention_slots', 0)
            tk.Label(row_frame, text=f"{retention}/3", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 9), width=widths[4]//8).pack(side='left', padx=2)
    
    def _create_footer(self):
        """Create footer with action buttons"""
        footer_frame = tk.Frame(self, bg=self.PANEL_COLOR, height=60)
        footer_frame.pack(fill='x')
        footer_frame.pack_propagate(False)
        
        # Close button
        tk.Button(footer_frame, text="Close Browser",
                 command=self.destroy,
                 bg='#6B7280', fg=self.TEXT_WHITE,
                 font=('Segoe UI', 12, 'bold'), 
                 padx=20, pady=8).pack(side='right', padx=20, pady=10)
        
        # Refresh button
        tk.Button(footer_frame, text="Refresh Data",
                 command=self._refresh_data,
                 bg=self.DEADLINE_GOLD, fg='black',
                 font=('Segoe UI', 12, 'bold'),
                 padx=20, pady=8).pack(side='right', padx=10, pady=10)
    
    def _refresh_data(self):
        """Refresh market data"""
        # In a real implementation, this would refresh all data
        print("Market data refreshed!")
        
    def _create_intelligence_panel(self, parent):
        """Create right panel with market intelligence"""
        # Right column
        right_frame = ttk.Frame(parent, style='Deadline.TFrame')
        right_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Intelligence Header
        intel_header = ttk.Label(right_frame, 
                                text="TRADE INTELLIGENCE", 
                                style='DeadlineSubtitle.TLabel')
        intel_header.pack(pady=(0, 15))
        
        # Trade rumors
        self._create_rumors_section(right_frame)
        
        # Market temperature
        self._create_market_temp_section(right_frame)
        
    def _create_rumors_section(self, parent):
        """Create trade rumors section"""
        rumors_frame = ttk.Frame(parent, style='Deadline.TFrame')
        rumors_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(rumors_frame, 
                 text="TRADE RUMORS", 
                 style='DeadlineSubtitle.TLabel').pack(pady=(0, 10))
        
        # Rumors text area
        rumors_text = tk.Text(rumors_frame, 
                             height=8, 
                             bg=self.NEUTRAL_GRAY, 
                             fg=self.TEXT_WHITE,
                             font=('Segoe UI', 9),
                             wrap='word')
        rumors_text.pack(fill='x')
        
        # Add rumors
        for rumor in self.trade_rumors:
            rumors_text.insert('end', f"• {rumor}\n\n")
        
        rumors_text.config(state='disabled')
        
    def _create_market_temp_section(self, parent):
        """Create market temperature indicators using real market data"""
        temp_frame = ttk.Frame(parent, style='Deadline.TFrame')
        temp_frame.pack(fill='both', expand=True)
        
        ttk.Label(temp_frame, 
                 text="MARKET TEMPERATURE", 
                 style='DeadlineSubtitle.TLabel').pack(pady=(0, 10))
        
        # Get real market temperature from deadline manager
        market_temp = self.deadline_manager.get_market_temperature()
        
        # Temperature mapping
        temp_indicators = {
            'cold': ('❄️', '#64B5F6'),
            'warm': ('🟡', '#FFB300'),  
            'hot': ('🔥', '#FF5722'),
            'blazing': ('💥', '#D32F2F')
        }
        
        # Display market temperature for each position
        positions_display = [
            ('FORWARDS', market_temp['forwards']),
            ('DEFENSEMEN', market_temp['defensemen']),
            ('GOALIES', market_temp['goalies'])
        ]
        
        for position, temp_level in positions_display:
            temp_icon, temp_color = temp_indicators.get(temp_level, ('⚪', '#757575'))
            
            pos_frame = tk.Frame(temp_frame, bg=self.NEUTRAL_GRAY, relief='sunken', bd=2)
            pos_frame.pack(fill='x', pady=5)
            
            tk.Label(pos_frame, text=position, bg=self.NEUTRAL_GRAY, fg=self.TEXT_WHITE, 
                    font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10)
            tk.Label(pos_frame, text=temp_icon, bg=self.NEUTRAL_GRAY, 
                    font=('Segoe UI', 14)).pack(side='right', padx=5)
            tk.Label(pos_frame, text=temp_level.upper(), bg=self.NEUTRAL_GRAY, 
                    fg=temp_color, font=('Segoe UI', 9, 'bold')).pack(side='right', padx=10)
        
    def _create_footer(self, parent):
        """Create footer with deadline status"""
        footer_frame = ttk.Frame(parent, style='Deadline.TFrame')
        footer_frame.pack(fill='x', pady=(20, 0))
        
        # Status bar
        status_frame = tk.Frame(footer_frame, bg=self.URGENT_RED, height=30)
        status_frame.pack(fill='x')
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, 
                                   text="TRADE DEADLINE ACTIVE - All trades must be completed before 3:00 PM ET", 
                                   bg=self.URGENT_RED, 
                                   fg=self.TEXT_WHITE, 
                                   font=('Segoe UI', 12, 'bold'))
        self.status_label.pack(expand=True, fill='both')
        
    def _start_animations(self):
        """Start all animated elements"""
        self._update_countdown()
        self._animate_ticker()
        self._generate_auto_trades()
        
    def _update_countdown(self):
        """Update countdown timer using real deadline manager data"""
        if self.deadline_passed:
            return
            
        # Use deadline manager for accurate time calculation
        time_info = self.deadline_manager.get_time_until_deadline()
        
        if time_info['expired']:
            self.deadline_passed = True
            self.countdown_label.config(text="DEADLINE PASSED", foreground=self.NEUTRAL_GRAY)
            self.status_label.config(text="TRADE DEADLINE HAS PASSED - No more trades allowed", 
                                   bg=self.NEUTRAL_GRAY)
            self.auto_trades_active = False
            return
        
        countdown_text = time_info['formatted']
        
        # Use urgency level for visual effects
        if time_info['urgency'] == 'critical':
            # Flash red when critical (under 1 hour)
            self.countdown_flash = not self.countdown_flash
            color = self.URGENT_RED if self.countdown_flash else self.DEADLINE_GOLD
            self.countdown_label.config(text=countdown_text, foreground=color)
        elif time_info['urgency'] == 'high':
            # Solid red when under 6 hours
            self.countdown_label.config(text=countdown_text, foreground=self.URGENT_RED)
        else:
            # Gold for normal time
            self.countdown_label.config(text=countdown_text, foreground=self.DEADLINE_GOLD)
        
        # Schedule next update
        self.after(1000, self._update_countdown)
        
    def _animate_ticker(self):
        """Animate the scrolling ticker"""
        if self.deadline_passed:
            return
            
        # Move ticker text
        self.ticker_position -= 2
        if self.ticker_position < -800:  # Reset when text scrolls off
            self.ticker_position = self.winfo_width()
            
        self.ticker_label.place(x=self.ticker_position, y=10)
        
        # Schedule next animation frame
        self.after(50, self._animate_ticker)
        
    def _generate_auto_trades(self):
        """Generate automatic trade notifications using deadline manager"""
        if not self.auto_trades_active or self.deadline_passed:
            return
            
        # Use deadline manager to generate realistic trade activity
        generated_activity = self.deadline_manager.generate_trade_activity()
        
        # Add generated trades to recent trades and ticker
        for activity in generated_activity:
            self._add_breaking_trade(activity['description'])
        
        # Schedule next check (frequency based on time to deadline)
        time_info = self.deadline_manager.get_time_until_deadline()
        if time_info['urgency'] == 'critical':
            next_check = 2000  # Every 2 seconds when critical
        elif time_info['urgency'] == 'high':
            next_check = 5000  # Every 5 seconds when high urgency
        else:
            next_check = 10000  # Every 10 seconds normally
            
        self.after(next_check, self._generate_auto_trades)
        
    def _add_breaking_trade(self, trade_description=None):
        """Add a breaking trade notification"""
        if trade_description:
            # Use provided trade description from deadline manager
            trade = f"🚨 BREAKING: {trade_description}"
        else:
            # Fallback to sample trades for testing
            sample_breaking_trades = [
                "Lightning trade veteran forward to Rangers!",
                "Bruins acquire defenseman from Senators!",
                "Maple Leafs land rental forward from Arizona!",
                "Avalanche add goaltender from Red Wings!",
                "Panthers trade expiring contract to Vegas!"
            ]
            trade_text = random.choice(sample_breaking_trades)
            trade = f"🚨 BREAKING: {trade_text}"
        
        # Update ticker
        current_text = self.ticker_label.cget('text')
        new_text = f"{current_text} --- {trade}"
        self.ticker_label.config(text=new_text)
        
    # Button command methods (placeholders for now)
    def _open_emergency_trade(self):
        """Open emergency trade interface"""
        if hasattr(self.parent, 'open_trade_window'):
            self.parent.open_trade_window()
        
    def _open_quick_proposals(self):
        """Open quick trade proposals"""
        # Placeholder - could open simplified trade interface
        pass
        
    def _open_market_analysis(self):
        """Open market analysis window"""
        # Placeholder - could show detailed market data
        pass
        
    def _close_deadline_center(self):
        """Close the trade deadline center"""
        self.auto_trades_active = False
        self.destroy()


def is_trade_deadline_day():
    """Check if today is trade deadline day (March 8th for this season)"""
    # Use the deadline manager for consistent logic
    manager = get_deadline_manager()
    return manager.is_trade_deadline_day()


def create_trade_deadline_button(parent_frame, parent_app):
    """Create trade deadline center access button (only visible on deadline day)"""
    if not is_trade_deadline_day():
        return None
        
    deadline_btn = tk.Button(
        parent_frame,
        text="TRADE DEADLINE CENTER",
        bg='#FF1744',
        fg='white',
        font=('Segoe UI', 14, 'bold'),
        relief='raised',
        bd=3,
        command=lambda: TradeDeadlineCenter(parent_app)
    )
    
    return deadline_btn


if __name__ == "__main__":
    # Test the Trade Deadline Center
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    # Create and show trade deadline center
    deadline_center = TradeDeadlineCenter(root)
    
    root.mainloop()
