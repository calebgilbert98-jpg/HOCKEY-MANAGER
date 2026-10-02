# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Trade Deadline Center - Immersive Trade Deadline Day Experience
Accessible only on trade deadline day (derived: 40 days before the last
regular-season game, per the CBA; Mar 8 fallback)
"""

import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime, timedelta
import random

# Import the trade deadline manager for backend logic
from trade_deadline_manager import get_deadline_manager

# Media rumor engine: rumors + impact availability generated from real
# league state (read-only). Replaces the old hardcoded fictional content.
import media_rumors


# -- Gating Phase 2: shared palette. _create_styles() aliases this so the
# views and the widget style names read from one source of truth. -----
_DEADLINE_COLORS = {
    "DEADLINE_BG": '#0e0e11',      # Charcoal background
    "URGENT_RED": '#00ceb8',       # Teal accent
    "DEADLINE_RED": '#00ceb8',     # Alias for accent
    "DEADLINE_GOLD": '#00ceb8',    # Teal for highlights
    "NEUTRAL_GRAY": '#1e1e24',     # Card surface for inactive elements
    "TEXT_WHITE": '#FFFFFF',       # White text
    "SUCCESS_GREEN": '#3DDC84',    # Green for completed trades
    "PANEL_COLOR": '#16161a',      # Panel background
    "BORDER_COLOR": '#2a2a30',     # Borders
}


class _DeadlineScreenBase(tk.Frame):
    """Tier-1 screen base for the deadline family (Gating Phase 2).

    The old classes were InGamePopup Toplevels opened by a factory. They
    are now screens built by ``show_screen`` as
    ``view_cls(holder, *args, app=app)``; the Toplevel API below is kept as
    no-op shims so the shared layout code works unchanged. Views are
    destroyed on navigation like any other screen, so every ``after()``
    loop must guard ``winfo_exists()``.
    """

    def __init__(self, parent, app=None):
        tk.Frame.__init__(self, parent)
        _app = app if app is not None else getattr(parent, "app", parent)
        self.app = _app
        # Historical: the old code read self.parent.<app attribute>.
        self.parent = _app
        self._close_screen = None  # set by show_screen()

    # -- Toplevel shims ------------------------------------------------
    def title(self, _text=None):
        return None

    def geometry(self, _spec=None):
        return ""

    def resizable(self, _w=None, _h=None):
        return None

    def attributes(self, *_args):
        return None

    def transient(self, _master=None):
        return None

    def protocol(self, _name=None, _func=None):
        return None

    def state(self, _s=None):
        return None

    def close_view(self):
        """Leave the screen (the navbar's ‹ Dashboard in screen mode)."""
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            try:
                self.destroy()
            except Exception:
                pass


class TradeDeadlineCenter(_DeadlineScreenBase):
    """Immersive Trade Deadline Center - Active only on Trade Deadline Day"""
    
    def __init__(self, parent, app=None):
        _DeadlineScreenBase.__init__(self, parent, app=app)

        # Initialize trade deadline manager
        self.deadline_manager = get_deadline_manager(getattr(self.app, 'game_manager', None))
        
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
        # Rumors are generated from real league state by the media rumor
        # engine (media_rumors.py): stable per in-game day, ~1 in 4 carries
        # a systematic distortion ("the media is wrong sometimes").
        self.trade_rumors = media_rumors.generate_rumors(
            deadline_manager=self.deadline_manager)
        
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
        """Configure the screen with immersive design (Tier-1: no topmost,
        no WM_DELETE -- the navbar owns close; the footer button still
        calls _close_deadline_center)."""
        self.configure(bg='#0e0e11')  # Charcoal background

        
    def _close_deadline_center(self):
        """Close the trade deadline center"""
        self.auto_trades_active = False
        self.close_view()

    def _create_intelligence_panel(self, parent):
        """Right column: league intelligence - rumors and buyers/sellers"""
        panel = tk.Frame(parent, bg=self.PANEL_COLOR, relief='raised', bd=2)
        panel.pack(side='right', fill='both', expand=True, padx=(10, 0))

        tk.Label(panel, text="LEAGUE INTELLIGENCE", bg=self.PANEL_COLOR,
                 fg=self.DEADLINE_GOLD, font=('Segoe UI', 13, 'bold')).pack(pady=(10, 6))

        self._create_stance_panel(panel)

        tk.Label(panel, text="Latest Rumors", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=12)
        rumors_box = tk.Text(panel, bg=self.DEADLINE_BG, fg=self.TEXT_WHITE, height=9,
                             font=('Segoe UI', 10), wrap='word', relief='flat',
                             highlightthickness=0)
        rumors_box.pack(fill='x', padx=12, pady=(4, 10))
        for rumor in getattr(self, 'trade_rumors', []):
            rumors_box.insert('end', f"\u2022 {rumor}\n\n")
        rumors_box.config(state='disabled')
        self._rumors_box = rumors_box  # for refresh without rebuilding

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

    # -- your deadline stance ------------------------------------------------
    def _resolve_user_team(self):
        """Find the user's team via the deadline manager's game manager."""
        try:
            gm = getattr(self.deadline_manager, 'game_manager', None)
            team = getattr(gm, 'user_team', None)
            if team:
                return team
            league = getattr(gm, 'league', None)
            teams = getattr(league, 'teams', None) or []
            for t in teams:
                try:
                    if getattr(t, 'is_user_team', False):
                        return t
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _league_teams(self):
        """Real Team objects from the league, or []."""
        try:
            gm = getattr(self.deadline_manager, 'game_manager', None)
            league = getattr(gm, 'league', None)
            teams = getattr(league, 'teams', None) or []
            return [t for t in teams if hasattr(t, 'wins') and hasattr(t, 'team_name')]
        except Exception:
            return []

    @staticmethod
    def _team_points(team):
        try:
            return 2 * int(getattr(team, 'wins', 0)) + int(getattr(team, 'ot_losses', 0))
        except Exception:
            return 0

    def _compute_stance(self):
        """Buyer/seller/tweener verdict + positional needs + cap space.

        All from real team data; returns None when no team is available.
        """
        team = self._resolve_user_team()
        if team is None:
            return None
        teams = self._league_teams()
        ordered = sorted(teams, key=self._team_points, reverse=True)
        rank = None
        for i, t in enumerate(ordered):
            if t is team or getattr(t, 'team_name', None) == getattr(team, 'team_name', None):
                rank = i + 1
                break
        n = len(ordered)
        games = int(getattr(team, 'wins', 0)) + int(getattr(team, 'losses', 0)) + int(getattr(team, 'ot_losses', 0))
        pts = self._team_points(team)

        if rank is None or n < 2 or games == 0:
            verdict, reason = "TBD", "Season hasn't started - no standings data yet."
        elif rank / n <= 1 / 3:
            verdict, reason = "BUYER", f"{rank} of {n} in the standings - a contender should load up."
        elif rank / n >= 2 / 3:
            verdict, reason = "SELLER", f"{rank} of {n} in the standings - sell rentals, stockpile picks."
        else:
            verdict, reason = "TWEENER", f"{rank} of {n} in the standings - one move either way."

        # Positional needs: roster groups by weakest average OVR
        needs = []
        try:
            groups = {"Forwards": ("C", "LW", "RW"), "Defense": ("LD", "RD", "D"), "Goalies": ("G",)}
            roster = list(getattr(team, 'roster', []) or [])
            avgs = []
            for gname, codes in groups.items():
                ovrs = []
                for pl in roster:
                    pp = getattr(pl, 'primary_position', None)
                    code = getattr(pp, 'value', str(pp))
                    if code in codes:
                        try:
                            ovrs.append(pl.overall_rating())
                        except Exception:
                            pass
                if ovrs:
                    avgs.append((gname, sum(ovrs) / len(ovrs), len(ovrs)))
            avgs.sort(key=lambda x: x[1])
            needs = [(g, a, c) for g, a, c in avgs[:2]]
        except Exception:
            needs = []

        # Cap space
        try:
            cap_space = int(getattr(team, 'cap_space', 0) or 0)
        except Exception:
            cap_space = None

        record = ""
        try:
            record = str(getattr(team, 'record_string', '')) or ""
        except Exception:
            pass
        return {
            'team_name': str(getattr(team, 'team_name', 'Your team')),
            'verdict': verdict, 'reason': reason, 'rank': rank, 'of': n,
            'record': record, 'points': pts, 'needs': needs, 'cap_space': cap_space,
        }

    def _create_stance_panel(self, panel):
        """'Your Deadline Stance' block at the top of the intelligence column."""
        info = self._compute_stance()
        box = tk.Frame(panel, bg=self.DEADLINE_BG, highlightbackground=self.BORDER_COLOR,
                       highlightthickness=1)
        box.pack(fill='x', padx=12, pady=(4, 12))
        tk.Label(box, text="YOUR DEADLINE STANCE", bg=self.DEADLINE_BG,
                 fg=self.DEADLINE_GOLD, font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        if info is None:
            tk.Label(box, text="No team data available.", bg=self.DEADLINE_BG,
                     fg=self.TEXT_WHITE, font=('Segoe UI', 10)).pack(anchor='w', padx=10, pady=(0, 8))
            return
        colors = {'BUYER': '#3DDC84', 'SELLER': '#FF5A5A', 'TWEENER': '#e0a13c', 'TBD': '#9aa0aa'}
        vcolor = colors.get(info['verdict'], '#9aa0aa')
        head = tk.Frame(box, bg=self.DEADLINE_BG)
        head.pack(fill='x', padx=10, pady=(0, 2))
        tk.Label(head, text=info['verdict'], bg=vcolor, fg='#0e0e11',
                 font=('Segoe UI', 11, 'bold'), padx=10, pady=2).pack(side='left')
        sub = f"{info['team_name']}"
        if info['record']:
            sub += f"  \u00b7  {info['record']}"
        if info['rank']:
            sub += f"  \u00b7  {info['rank']} of {info['of']} ({info['points']} pts)"
        tk.Label(head, text=sub, bg=self.DEADLINE_BG, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 10)).pack(side='left', padx=(8, 0))
        tk.Label(box, text=info['reason'], bg=self.DEADLINE_BG, fg='#9aa0aa',
                 font=('Segoe UI', 10), wraplength=380, justify='left',
                 anchor='w').pack(anchor='w', padx=10, pady=(0, 4))
        if info['needs']:
            need_txt = "Biggest needs: " + ", ".join(
                f"{g} (avg {a:.0f}, {c} on roster)" for g, a, c in info['needs'])
            tk.Label(box, text=need_txt, bg=self.DEADLINE_BG, fg=self.TEXT_WHITE,
                     font=('Segoe UI', 10), wraplength=380, justify='left',
                     anchor='w').pack(anchor='w', padx=10, pady=(0, 2))
        if info['cap_space'] is not None:
            cs = info['cap_space']
            cs_txt = f"Cap space: ${cs/1e6:.1f}M"
            cs_fg = '#3DDC84' if cs > 0 else '#FF5A5A'
            tk.Label(box, text=cs_txt, bg=self.DEADLINE_BG, fg=cs_fg,
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=10, pady=(0, 8))
        else:
            tk.Label(box, text="Cap space: --", bg=self.DEADLINE_BG, fg='#9aa0aa',
                     font=('Segoe UI', 10)).pack(anchor='w', padx=10, pady=(0, 8))

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

    def refresh(self):
        """Refresh countdown/ticker on demand (called after each 30-min tick)."""
        try:
            self._update_countdown()
        except Exception:
            pass

    def _update_countdown(self):
        """Update the countdown timer each second.

        On deadline day the countdown follows the game clock (30-minute
        increments toward 3 PM ET); otherwise the wall-clock estimate.
        """
        if getattr(self, 'deadline_passed', False):
            return
        try:
            time_info = self.deadline_manager.get_time_until_deadline()
            if time_info.get('expired'):
                self.deadline_passed = True
                self.countdown_label.config(text="DEADLINE PASSED", foreground=self.NEUTRAL_GRAY)
                self.status_label.config(text="TRADE DEADLINE HAS PASSED - No more trades allowed")
                return
            text = time_info.get('formatted', '--:--:--')
            if time_info.get('game_clock'):
                text = f"{time_info['game_clock']}  ·  {text} left"
            self.countdown_label.config(text=text)
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

        # Deadline theme colors (Gating Phase 2: hoisted to
        # _DEADLINE_COLORS; the exact values are unchanged).
        for _k, _v in _DEADLINE_COLORS.items():
            setattr(self, _k, _v)
        
        # Custom styles
        style.configure('Deadline.TFrame', background=self.DEADLINE_BG)
        style.configure('DeadlineTitle.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.URGENT_RED, 
                       font=('Segoe UI', 20, 'bold'))
        style.configure('DeadlineSubtitle.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.TEXT_WHITE, 
                       font=('Segoe UI', 12))
        style.configure('CountdownLabel.TLabel', 
                       background=self.DEADLINE_BG, 
                       foreground=self.DEADLINE_GOLD, 
                       font=('Consolas', 32, 'bold'))
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
            text="QUICK TRADE",
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

        # Advance the deadline clock 30 minutes (same as Continue)
        advance_btn = tk.Button(
            buttons_frame,
            text="ADVANCE 30 MIN ⏩",
            command=self._advance_deadline_clock,
            bg='#1d4ed8',
            fg=self.TEXT_WHITE,
            font=('Segoe UI', 10, 'bold'),
            relief='raised',
            bd=3,
            padx=20,
            pady=8
        )
        advance_btn.pack(side='left', padx=5)
        
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
            text="BROWSE MARKET",
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
        news_overlay = tk.Frame(self, bg='#00ceb8', relief='raised', bd=3)
        news_overlay.place(relx=0.5, rely=0.1, anchor='center', 
                          relwidth=0.8, height=60)
        
        # Breaking news label
        breaking_label = tk.Label(news_overlay, text="BREAKING NEWS",
                                 bg='#00ceb8', fg='white',
                                 font=('Segoe UI', 12, 'bold'))
        breaking_label.pack(pady=2)
        
        # News content
        news_label = tk.Label(news_overlay, text=news_item,
                             bg='#00ceb8', fg='white',
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
            new_bg = '#00a894' if current_bg == '#00ceb8' else '#00ceb8'
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
        """Create movement statistics display.

        Real deadline-day stats from the deadline manager. When a value is
        absent (e.g. no deals completed yet), show an honest "--" -- never
        a fabricated random number.
        """
        stats_container = tk.Frame(parent, bg=self.PANEL_COLOR)
        stats_container.pack(fill='x', padx=5, pady=5)

        # Get movement data from deadline manager
        deadline_summary = self.deadline_manager.get_deadline_summary()
        stats = deadline_summary.get('statistics', {})

        # Movement metrics -- real values only; "--" when not yet known
        def _fmt(value, money=False):
            if value is None:
                return "--"
            try:
                if money and not int(value):
                    return "--"
            except Exception:
                return "--"
            return f"${value}M" if money else str(value)

        movements_today = _fmt(stats.get('players_moved'))
        trades_today = _fmt(stats.get('total_trades'))
        biggest_deal = _fmt(stats.get('biggest_deal_value'), money=True)
        
        metrics = [
            ("Players Moved Today", movements_today, self.SUCCESS_GREEN),
            ("Trades Completed", trades_today, self.DEADLINE_GOLD),
            ("Biggest Deal Value", biggest_deal, self.URGENT_RED)
        ]
        
        for i, (label, value, color) in enumerate(metrics):
            metric_frame = tk.Frame(stats_container, bg=self.PANEL_COLOR)
            metric_frame.pack(side='left' if i < 2 else 'right', fill='x', expand=True, padx=5)
            
            tk.Label(metric_frame, text=value, bg=self.PANEL_COLOR, fg=color,
                    font=('Segoe UI', 14, 'bold')).pack()
            tk.Label(metric_frame, text=label, bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                    font=('Segoe UI', 8)).pack()
    
    def _create_impact_players_list(self, parent):
        """Create list of high-impact players potentially available.

        Derived from real availability by the media rumor engine: players
        actually on trade blocks (AI + user), expiring contracts on sellers,
        and unhappy quality players. No real-life names, nothing hardcoded.
        """
        players_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        players_frame.pack(fill='both', expand=True, padx=5, pady=5)

        impact_players = media_rumors.get_impact_players(
            deadline_manager=self.deadline_manager)
        if not impact_players:
            # Honest placeholder when nothing is actually available
            impact_players = [
                {"name": "--", "pos": "--", "team": "--",
                 "status": "Possible", "value": "Low"},
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
        # Gating Phase 2: Tier-1 screen (own screen id so the navbar
        # jump is tracked like any other screen).
        self.app.show_screen("deadline_quick_trade", "Quick Trade",
                             QuickTradeInterface, self.deadline_manager)

    def _open_emergency_trade(self):
        """Open emergency trade interface for last-minute deals"""
        self.app.show_screen("deadline_emergency_trade", "Emergency Trade",
                             EmergencyTradeInterface, self.deadline_manager)

    def _advance_deadline_clock(self):
        """Advance the deadline-day game clock 30 minutes (same as Continue)."""
        try:
            self.parent.simulate_day()
        except Exception as e:
            print(f"deadline clock advance failed: {e}")
    
    def _open_market_browser(self):
        """Open comprehensive market browser"""
        self.app.show_screen("deadline_market", "Deadline Market",
                             DeadlineMarketBrowser, self.deadline_manager)


class QuickTradeInterface(_DeadlineScreenBase):
    """Quick trade proposal interface for deadline day.

    Everything reads live league state: the partner list is every NHL
    team except yours (sorted, scrollable -- not a hardcoded five), "Their
    Offer" lists the selected partner's real trade block, "Your Offer"
    lists your real tradeable picks and expiring contracts, the
    evaluation runs the real trade engine, and SEND PROPOSAL submits
    through the real negotiation machinery (trade_negotiation.send_offer)
    -- the AI answers instantly on deadline day, and the confirmation
    reflects the negotiation's real post-send status. Non-modal: closing
    the card defers, never sends.
    """

    _QT_SESSION_ID = "deadline_quick_trade"

    def __init__(self, parent, deadline_manager, app=None):
        _DeadlineScreenBase.__init__(self, parent, app=app)
        self.deadline_manager = deadline_manager

        # Colors: center-palette constants (the old code read them from the
        # center card; the frame background still comes from the app).
        self.BG_COLOR = (getattr(self.app, 'BG_COLOR', None)
                         or _DEADLINE_COLORS["DEADLINE_BG"])
        self.PANEL_COLOR = _DEADLINE_COLORS["PANEL_COLOR"]
        self.TEXT_WHITE = _DEADLINE_COLORS["TEXT_WHITE"]
        self.DEADLINE_GOLD = _DEADLINE_COLORS["DEADLINE_GOLD"]
        self.URGENT_RED = _DEADLINE_COLORS["URGENT_RED"]

        gm = getattr(self.app, 'game_manager', None) if self.app else None
        self.league = getattr(gm, 'league', None)
        self.user_team = getattr(self.app, 'user_team', None) \
            if self.app else None

        self.partner_team = None
        self.user_assets = []      # real Player / DraftPick objects (yours)
        self.partner_assets = []   # real Player objects (theirs)
        self._your_pool = []       # [(label, asset)] you can offer
        self._their_pool = []      # [(label, asset)] from partner's block
        self._team_objs = {}

        self._setup_window()
        self._create_interface()
        # Gating Phase 2: rebuild the parked quick proposal (§6).
        self._qt_restoring = False
        self._restore_qt_session()

    # -- context ------------------------------------------------------
    def _resolve_app(self):
        """Gating Phase 2: self.app is wired by the screen base already."""
        return self.app

    # -- Tier-B session ("deadline_quick_trade", kind "trade") ---------
    # The parked proposal (partner + asset ids) writes through on every
    # interaction and rebuilds on open with the ids revalidated against
    # live rosters/picks (§6). Nothing is ever sent implicitly.
    def _qt_session(self):
        from popup_system import get_pending_session
        sess = get_pending_session(self.app, self._QT_SESSION_ID)
        if not isinstance(sess, dict):
            return {}
        sess.setdefault("kind", "trade")
        return sess

    @staticmethod
    def _asset_ref(asset):
        # Same dict-ref convention as TradeWindow._asset_ref (JSON-safe).
        return {"id": str(getattr(asset, "id", "")), "kind": "player",
                "label": str(getattr(asset, "full_name",
                                     getattr(asset, "name", "?")))}

    def _snapshot_qt_session(self):
        if getattr(self, "_qt_restoring", False):
            return
        try:
            sess = self._qt_session()
            if not sess:
                return
            sess["partner_name"] = (getattr(self.partner_team, "team_name",
                                            "") or "")
            sess["user_assets"] = [self._asset_ref(a)
                                   for a in (self.user_assets or [])]
            sess["partner_assets"] = [self._asset_ref(a)
                                      for a in (self.partner_assets or [])]
        except Exception:
            pass

    def _clear_qt_session(self):
        try:
            sessions = getattr(self.app, "pending_sessions", None)
            if isinstance(sessions, dict):
                sessions.pop(self._QT_SESSION_ID, None)
        except Exception:
            pass

    def _restore_qt_session(self):
        try:
            sess = self._qt_session()
            if not sess or not sess.get("partner_name"):
                return
            self._qt_restoring = True
            try:
                pname = sess["partner_name"]
                # Select the partner in the listbox (drives _on_team_select,
                # which rebuilds their pool from live state).
                found = False
                try:
                    for i, name in enumerate(
                            self._team_listbox.get(0, 'end')):
                        if name == pname:
                            self._team_listbox.selection_clear(0, 'end')
                            self._team_listbox.selection_set(i)
                            self._team_listbox.see(i)
                            found = True
                            break
                except Exception:
                    pass
                if not found:
                    return  # partner gone: parked proposal is dead
                self._on_team_select()

                def _revalidate(refs, pool):
                    out = []
                    for ref in (refs or []):
                        _id = (ref.get("id") if isinstance(ref, dict)
                               else str(ref))
                        for _label, asset in (pool or []):
                            if str(getattr(asset, "id", "")) == str(_id):
                                out.append(asset)
                                break
                    return out

                user = _revalidate(sess.get("user_assets"), self._your_pool)
                partner = _revalidate(sess.get("partner_assets"),
                                      self._their_pool)
                dropped = ((len(sess.get("user_assets") or []) - len(user))
                           + (len(sess.get("partner_assets") or [])
                              - len(partner)))
                self.user_assets = user
                self.partner_assets = partner
                self._render_offer('user')
                self._render_offer('partner')
                self._update_evaluation()
                if dropped:
                    from popup_system import notify_card
                    notify_card(self, "Proposal changed",
                                f"{dropped} asset(s) are no longer "
                                f"available -- the workbench shows the live "
                                f"state.", kind="warning")
            finally:
                self._qt_restoring = False
        except Exception:
            pass
    def _nhl_partners(self):
        """Every NHL team except the user's, sorted -- real league state."""
        out = []
        for t in (getattr(self.league, 'teams', None) or []):
            try:
                if t is None or t is self.user_team:
                    continue
                ln = str(getattr(t, 'league_name', '') or '')
                if 'National Hockey League' in ln or 'NHL' in ln or not ln:
                    out.append(t)
            except Exception:
                continue
        return sorted(out, key=lambda t: str(getattr(t, 'team_name', '')))

    @staticmethod
    def _pos_code(p):
        try:
            pos = getattr(p, 'primary_position', None)
            return getattr(pos, 'value', None) or getattr(pos, 'name', '?')
        except Exception:
            return '?'

    @staticmethod
    def _ovr(p):
        try:
            return int(p.overall_rating())
        except Exception:
            return 0

    # -- window -------------------------------------------------------
    def _setup_window(self):
        """Setup screen properties (Tier-1: no Toplevel calls)."""
        self.configure(bg=self.BG_COLOR)
        # No grab_set: Eastside grammar -- the screen is non-modal and
        # dismissing it defers the proposal, never sends it.

    def _create_interface(self):
        """Create the quick trade interface"""
        # Header
        header = tk.Frame(self, bg=self.URGENT_RED, height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        try:
            remaining = self.deadline_manager.get_time_until_deadline().get(
                'formatted', '')
        except Exception:
            remaining = ''
        title = "QUICK TRADE" + (f" - {remaining} REMAINING" if remaining else "")
        tk.Label(header, text=title, bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 14, 'bold')).pack(expand=True)

        # Main content
        content = tk.Frame(self, bg=self.PANEL_COLOR)
        content.pack(fill='both', expand=True, padx=12, pady=12)

        # Trading team selection (live league)
        self._create_team_selector(content)

        # Asset columns
        self._create_asset_columns(content)

        # Trade evaluation (real engine)
        self._create_trade_evaluation(content)

        # Action buttons
        self._create_action_buttons(content)

        self._refresh_your_pool()
        self._update_evaluation()

    def _create_team_selector(self, parent):
        """Create team selection interface (live league teams)."""
        teams_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        teams_frame.pack(fill='x', pady=(0, 8))

        tk.Label(teams_frame, text="Select Trading Partner (live league):",
                 bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w')

        list_frame = tk.Frame(teams_frame, bg=self.PANEL_COLOR)
        list_frame.pack(fill='x', pady=6)
        self._team_listbox = tk.Listbox(
            list_frame, height=4, bg=self.BG_COLOR, fg=self.TEXT_WHITE,
            selectbackground=self.DEADLINE_GOLD, selectforeground='black',
            font=('Segoe UI', 10), exportselection=False)
        scrollbar = tk.Scrollbar(list_frame, orient='vertical',
                                 command=self._team_listbox.yview)
        self._team_listbox.configure(yscrollcommand=scrollbar.set)
        self._team_listbox.pack(side='left', fill='x', expand=True)
        scrollbar.pack(side='right', fill='y')

        for t in self._nhl_partners():
            name = str(getattr(t, 'team_name', ''))
            if not name:
                continue
            self._team_objs[name] = t
            self._team_listbox.insert('end', name)
        if not self._team_objs:
            self._team_listbox.insert('end', "(no league loaded)")
        self._team_listbox.bind('<<ListboxSelect>>', self._on_team_select)

    def _asset_column(self, parent, title, side):
        """One offer column: available pool + add/remove + chosen assets."""
        frame = tk.LabelFrame(parent, text=title, bg=self.PANEL_COLOR,
                              fg=self.TEXT_WHITE, font=('Segoe UI', 10, 'bold'))
        frame.pack(side=('left' if side == 'user' else 'right'),
                   fill='both', expand=True, padx=(0, 6) if side == 'user'
                   else (6, 0))

        tk.Label(frame, text="Available:", bg=self.PANEL_COLOR,
                 fg=self.TEXT_WHITE, font=('Segoe UI', 9)).pack(anchor='w',
                 padx=6, pady=(4, 0))
        pool_frame = tk.Frame(frame, bg=self.PANEL_COLOR)
        pool_frame.pack(fill='both', expand=True, padx=6)
        pool_lb = tk.Listbox(pool_frame, height=6, bg=self.BG_COLOR,
                             fg=self.TEXT_WHITE,
                             selectbackground=self.DEADLINE_GOLD,
                             selectforeground='black',
                             font=('Segoe UI', 9), exportselection=False)
        pool_sb = tk.Scrollbar(pool_frame, orient='vertical',
                               command=pool_lb.yview)
        pool_lb.configure(yscrollcommand=pool_sb.set)
        pool_lb.pack(side='left', fill='both', expand=True)
        pool_sb.pack(side='right', fill='y')

        btn_row = tk.Frame(frame, bg=self.PANEL_COLOR)
        btn_row.pack(fill='x', padx=6, pady=4)
        tk.Button(btn_row, text="Add \u25bc", bg=self.PANEL_COLOR,
                  fg=self.TEXT_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='ridge',
                  command=lambda: self._add_asset(side)).pack(side='left')
        tk.Button(btn_row, text="\u25b2 Remove", bg=self.PANEL_COLOR,
                  fg=self.TEXT_WHITE, font=('Segoe UI', 9),
                  relief='ridge',
                  command=lambda: self._remove_asset(side)).pack(side='right')

        tk.Label(frame, text="In proposal:", bg=self.PANEL_COLOR,
                 fg=self.TEXT_WHITE, font=('Segoe UI', 9)).pack(anchor='w',
                 padx=6)
        offer_frame = tk.Frame(frame, bg=self.PANEL_COLOR)
        offer_frame.pack(fill='x', padx=6, pady=(0, 6))
        offer_lb = tk.Listbox(offer_frame, height=3, bg=self.BG_COLOR,
                              fg=self.DEADLINE_GOLD, font=('Segoe UI', 9),
                              exportselection=False)
        offer_sb = tk.Scrollbar(offer_frame, orient='vertical',
                                command=offer_lb.yview)
        offer_lb.configure(yscrollcommand=offer_sb.set)
        offer_lb.pack(side='left', fill='x', expand=True)
        offer_sb.pack(side='right', fill='y')
        # EHM/FM24: right-click a player row for the player menu. Getters
        # resolve the listbox entry under the cursor to the live asset.
        try:
            self._bind_trade_listbox_context(pool_lb, side, 'pool')
            self._bind_trade_listbox_context(offer_lb, side, 'offer')
        except Exception:
            pass
        return pool_lb, offer_lb

    def _bind_trade_listbox_context(self, lb, side, kind):
        """Right-click a trade-listbox row -> player context menu."""
        try:
            from player_context_menu import bind_player_context
        except Exception:
            return
        try:
            from game_classes import DraftPick as _DraftPick
        except Exception:
            _DraftPick = ()

        def _player_only(asset):
            if asset is None or isinstance(asset, _DraftPick):
                return None
            return asset if hasattr(asset, 'full_name') else None

        def _getter(event, _lb=lb, _side=side, _kind=kind):
            try:
                idx = _lb.nearest(event.y)
            except Exception:
                return None
            if idx is None or idx < 0:
                return None
            try:
                if _kind == 'pool':
                    pool = (self._your_pool if _side == 'user'
                            else self._their_pool)
                    if idx >= len(pool):
                        return None
                    entry = pool[idx]
                    asset = (entry[1] if isinstance(entry, (tuple, list))
                             else entry)
                else:
                    assets = (self.user_assets if _side == 'user'
                              else self.partner_assets)
                    if idx >= len(assets):
                        return None
                    asset = assets[idx]
            except Exception:
                return None
            return _player_only(asset)

        bind_player_context(lb, _getter, self)

    def _create_asset_columns(self, parent):
        """Create the two asset columns."""
        cols = tk.Frame(parent, bg=self.PANEL_COLOR)
        cols.pack(fill='both', expand=True, pady=(0, 8))
        self._your_pool_list, self._your_offer_list = self._asset_column(
            cols, "Your Offer (your real picks & rentals)", 'user')
        self._their_pool_list, self._their_offer_list = self._asset_column(
            cols, "Their Offer (their real trade block)", 'partner')

    def _create_trade_evaluation(self, parent):
        """Create trade evaluation display (real engine numbers)."""
        eval_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='sunken',
                              bd=2)
        eval_frame.pack(fill='x', pady=(0, 8))

        tk.Label(eval_frame, text="Trade Evaluation (live engine)",
                 bg=self.PANEL_COLOR, fg=self.DEADLINE_GOLD,
                 font=('Segoe UI', 11, 'bold')).pack(pady=(6, 2))
        self._eval_label = tk.Label(eval_frame, text="Incomplete",
                                    bg=self.PANEL_COLOR, fg='#9CA3AF',
                                    font=('Segoe UI', 11, 'bold'))
        self._eval_label.pack()
        self._eval_detail = tk.Label(eval_frame, text="",
                                     bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                                     font=('Segoe UI', 9))
        self._eval_detail.pack(pady=(0, 6))

    def _create_action_buttons(self, parent):
        """Create action buttons"""
        buttons_frame = tk.Frame(parent, bg=self.PANEL_COLOR)
        buttons_frame.pack(fill='x')

        send_btn = tk.Button(buttons_frame, text="SEND PROPOSAL",
                             bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                             font=('Segoe UI', 12, 'bold'), padx=24, pady=8,
                             command=self._send_proposal)
        send_btn.pack(side='left', padx=(0, 10))

        full_btn = tk.Button(buttons_frame, text="FULL TRADE CENTER",
                             bg='#374151', fg=self.TEXT_WHITE,
                             font=('Segoe UI', 10, 'bold'), padx=16, pady=8,
                             command=self._open_full_trade_center)
        full_btn.pack(side='left')

        cancel_btn = tk.Button(buttons_frame, text="CANCEL",
                               bg='#6B7280', fg=self.TEXT_WHITE,
                               font=('Segoe UI', 12, 'bold'), padx=24, pady=8,
                               command=self.close_view)
        cancel_btn.pack(side='right')

    # -- live data ----------------------------------------------------
    def _refresh_your_pool(self):
        """Your real offerable assets: tradeable picks + expiring contracts."""
        import trade_engine as te
        pool = []
        if self.user_team is not None:
            # Tradeable picks (same rule as the full Trade Center:
            # still yours, not expired dead paper).
            for yr in sorted(getattr(self.user_team, 'draft_picks', {}) or {}):
                for pk in (self.user_team.draft_picks.get(yr) or []):
                    try:
                        if getattr(pk, 'current_team', '') != \
                                self.user_team.team_name:
                            continue
                        if hasattr(pk, 'can_be_traded') and \
                                not pk.can_be_traded():
                            continue
                    except Exception:
                        continue
                    try:
                        label = (f"{te.asset_label(pk)}  "
                                 f"[{te.asset_value(pk):,}]")
                    except Exception:
                        label = "Draft pick"
                    pool.append((label, pk))
            # Expiring contracts ("rentals"), best value first.
            rentals = []
            for p in (getattr(self.user_team, 'roster', None) or []):
                try:
                    if getattr(getattr(p, 'contract', None),
                               'years_remaining', 99) == 1:
                        rentals.append(p)
                except Exception:
                    continue
            try:
                rentals.sort(key=lambda p: te.asset_value(p), reverse=True)
            except Exception:
                pass
            for p in rentals[:12]:
                try:
                    val = te.asset_value(p)
                except Exception:
                    val = 0
                pool.append((
                    f"{getattr(p, 'full_name', '?')} "
                    f"({self._pos_code(p)}, {self._ovr(p)})  [{val:,}]", p))
        self._your_pool = pool
        self._render_listbox(self._your_pool_list,
                             [label for label, _ in pool],
                             empty="(no tradeable picks or rentals)")

    def _refresh_their_pool(self):
        """The selected partner's real trade block (league.trade_blocks)."""
        import trade_market as tmk
        import trade_engine as te
        pool = []
        if self.partner_team is not None and self.league is not None:
            try:
                tmk.refresh_trade_blocks(self.app, self.league)
            except Exception:
                pass
            try:
                blocks = tmk.get_trade_blocks(self.league)
            except Exception:
                blocks = {}
            tname = str(getattr(self.partner_team, 'team_name', ''))
            for pid in (blocks.get(tname, None) or []):
                try:
                    player, _team = tmk.resolve_player(self.league, pid)
                except Exception:
                    player = None
                if player is None:
                    continue
                try:
                    val = te.asset_value(player)
                except Exception:
                    val = 0
                pool.append((
                    f"{getattr(player, 'full_name', '?')} "
                    f"({self._pos_code(player)}, {self._ovr(player)})  "
                    f"[{val:,}]", player))
        self._their_pool = pool
        self._render_listbox(self._their_pool_list,
                             [label for label, _ in pool],
                             empty="(nothing on their block)")

    @staticmethod
    def _render_listbox(lb, labels, empty=""):
        lb.delete(0, 'end')
        if labels:
            for label in labels:
                lb.insert('end', label)
        elif empty:
            lb.insert('end', empty)

    def _asset_label(self, asset):
        try:
            import trade_engine as te
            from game_classes import DraftPick
            if isinstance(asset, DraftPick):
                return te.asset_label(asset)
        except Exception:
            pass
        try:
            return (f"{getattr(asset, 'full_name', '?')} "
                    f"({self._pos_code(asset)}, {self._ovr(asset)})")
        except Exception:
            return "?"

    def _render_offer(self, side):
        if side == 'user':
            assets, lb = self.user_assets, self._your_offer_list
        else:
            assets, lb = self.partner_assets, self._their_offer_list
        self._render_listbox(lb, [self._asset_label(a) for a in assets],
                             empty="(empty)")

    # -- interactions -------------------------------------------------
    def _on_team_select(self, event=None):
        """Handle team selection: load their real block into Their Offer."""
        sel = self._team_listbox.curselection()
        if not sel:
            return
        name = self._team_listbox.get(sel[0])
        self.partner_team = self._team_objs.get(name)
        # Their side resets: those assets belong to the old partner.
        self.partner_assets = []
        self._refresh_their_pool()
        self._render_offer('partner')
        self._update_evaluation()
        self._snapshot_qt_session()  # Gating P2: write-through

    def _add_asset(self, side):
        if side == 'user':
            pool, pool_lb, assets = (self._your_pool, self._your_pool_list,
                                     self.user_assets)
        else:
            pool, pool_lb, assets = (self._their_pool, self._their_pool_list,
                                     self.partner_assets)
        sel = pool_lb.curselection()
        if not sel or sel[0] >= len(pool):
            return
        _label, asset = pool[sel[0]]
        if not any(a is asset for a in assets):
            assets.append(asset)
        self._render_offer(side)
        self._update_evaluation()
        self._snapshot_qt_session()  # Gating P2: write-through

    def _remove_asset(self, side):
        if side == 'user':
            offer_lb, assets = self._your_offer_list, self.user_assets
        else:
            offer_lb, assets = self._their_offer_list, self.partner_assets
        sel = offer_lb.curselection()
        if not sel or sel[0] >= len(assets):
            return
        assets.pop(sel[0])
        self._render_offer(side)
        self._update_evaluation()
        self._snapshot_qt_session()  # Gating P2: write-through

    def _update_evaluation(self):
        """Run the real trade engine over the current proposal."""
        label, detail, color = "Incomplete", \
            "Add at least one asset to each side.", '#9CA3AF'
        try:
            import trade_engine as te
            ev = te.evaluate_trade(self.user_assets, self.partner_assets,
                                   user_team=self.user_team,
                                   partner_team=self.partner_team)
            if self.user_assets and self.partner_assets:
                label = ev.label
                detail = (f"Your value: {ev.user_value:,}   |   "
                          f"Their value: {ev.partner_value:,}")
                color = {'Fair deal': '#10B981', 'You overpay': self.URGENT_RED,
                         'They overpay': self.DEADLINE_GOLD}.get(
                    label, self.TEXT_WHITE)
            else:
                detail = (f"Your value: {ev.user_value:,}   |   "
                          f"Their value: {ev.partner_value:,}")
        except Exception:
            label, detail, color = "Unavailable", "", '#9CA3AF'
        self._eval_label.config(text=label, fg=color)
        self._eval_detail.config(text=detail)

    def _open_full_trade_center(self):
        """Route to the real full trade workbench."""
        try:
            opener = getattr(self.app, 'open_trade_window', None)
            if callable(opener):
                opener()
            else:
                from popup_system import messagebox  # gating T2-Phase 0: in-game card, not OS-modal
                messagebox.showinfo("Trade Center",
                                    "The full Trade Center is unavailable "
                                    "right now.")
        except Exception:
            pass

    def _send_proposal(self):
        """Send the proposal through the real negotiation machinery."""
        from popup_system import messagebox  # gating T2-Phase 0: in-game card, not OS-modal
        if self.app is None or self.user_team is None:
            messagebox.showwarning("No League",
                                   "No league loaded -- cannot send a proposal.")
            return
        if self.partner_team is None:
            messagebox.showwarning("No Partner",
                                   "Select a trading partner first.")
            return
        if not self.user_assets or not self.partner_assets:
            messagebox.showwarning(
                "Incomplete",
                "Add at least one asset to each side of the deal first.")
            return
        # Gating Phase 2 (§6): consume-once -- a double-click must not send
        # the same proposal twice.
        if getattr(self, "_qt_sent", False):
            return
        # No-trade clauses block the deal before it leaves the building --
        # say so honestly instead of sending a dead proposal.
        try:
            import trade_engine as te
            vetoes = te.trade_vetoes(self.user_team, self.partner_team,
                                     self.user_assets, league=self.league)
        except Exception:
            vetoes = []
        if vetoes:
            names = ", ".join(
                str(getattr(v.get('player'), 'full_name', '?'))
                for v in vetoes[:3])
            messagebox.showwarning(
                "No-trade protection",
                f"{names} cannot be moved to "
                f"{getattr(self.partner_team, 'team_name', 'them')} "
                f"({vetoes[0].get('clause', 'clause')} protection).\n\n"
                "Remove them from the offer, or ask for a waiver in the "
                "full Trade Center.")
            return
        # Gating Phase 2 (§6): transactional cap revalidation at the moment
        # of send -- the cap may have moved since the workbench was built.
        try:
            import trade_engine as te
            if not te._cap_ok_after(self.user_team, self.user_assets,
                                    self.partner_assets):
                messagebox.showwarning(
                    "Cap check",
                    "The deal no longer fits under the salary cap -- "
                    "your roster moved since the proposal was built. "
                    "Adjust the offer and try again.")
                return
        except Exception:
            pass
        try:
            import trade_negotiation as tn
            neg = tn.send_offer(self.app, self.partner_team,
                                list(self.user_assets),
                                list(self.partner_assets))
        except Exception as e:
            messagebox.showwarning("Send failed",
                                   f"Could not send the proposal: {e}")
            return
        self._qt_sent = True  # consume-once: the deal is in the inbox now
        # Confirmation reflects real post-send state: on deadline day the
        # AI answers instantly, so read the negotiation's actual status.
        pname = str(getattr(self.partner_team, 'team_name', 'them'))
        try:
            you = tn.asset_summary(neg.user_assets)
            them = tn.asset_summary(neg.partner_assets)
        except Exception:
            you, them = "your assets", "their assets"
        status = str(getattr(neg, 'status', 'awaiting_ai'))
        if status == 'accepted':
            title = "Deal accepted!"
            body = (f"{pname} accepted your offer on the spot.\n\n"
                    f"YOU SEND: {you}\nYOU GET: {them}")
        elif status == 'declined':
            title = "Offer declined"
            body = (f"{pname} turned the offer down.\n\n"
                    f"YOU OFFERED: {you}\nYOU ASKED FOR: {them}\n\n"
                    "Their reply is in your inbox.")
        elif status == 'awaiting_user':
            title = "Counter-offer waiting"
            body = (f"{pname} countered instantly -- answer it from your "
                    f"inbox.\n\nYOUR OFFER: {you} for {them}")
        else:
            title = "Offer sent"
            body = (f"Your offer is with {pname}'s front office.\n\n"
                    f"YOU SEND: {you}\nYOU GET: {them}\n\n"
                    "The reply will land in your inbox.")
        messagebox.showinfo(title, body)
        # Gating Phase 2: the proposal is parked no more -- clear the
        # session and leave the screen (close_view is a no-op-safe shim
        # only when the navbar owns the view).
        self._clear_qt_session()
        self.close_view()


class EmergencyTradeInterface(_DeadlineScreenBase):
    """Emergency trade interface for last-minute deadline deals.

    Only real one-click actions survive here:

    - "Fire Sale": lists your expiring contracts on the trade block via
      the real trade_market store (source 'user_block'), so AI GMs can
      bid on them immediately.

    The old "Accept Any Reasonable Offer" was cut: no auto-accept
    machinery exists anywhere in the codebase. The old "Deadline
    Extension Request" was cut: the deadline is CBA-derived and final --
    no extension can be requested. Non-modal: no grab_set; closing the
    card defers, nothing happens implicitly.
    """

    def __init__(self, parent, deadline_manager, app=None):
        _DeadlineScreenBase.__init__(self, parent, app=app)
        self.deadline_manager = deadline_manager

        # Colors: center-palette constants (the old code read them from the
        # center card; the frame background still comes from the app).
        self.BG_COLOR = (getattr(self.app, 'BG_COLOR', None)
                         or _DEADLINE_COLORS["DEADLINE_BG"])
        self.PANEL_COLOR = _DEADLINE_COLORS["PANEL_COLOR"]
        self.TEXT_WHITE = _DEADLINE_COLORS["TEXT_WHITE"]
        self.DEADLINE_RED = _DEADLINE_COLORS["DEADLINE_RED"]
        self.URGENT_RED = _DEADLINE_COLORS["URGENT_RED"]

        gm = getattr(self.app, 'game_manager', None) if self.app else None
        self.league = getattr(gm, 'league', None)
        self.user_team = getattr(self.app, 'user_team', None) \
            if self.app else None

        self._setup_window()
        self._create_interface()

    def _resolve_app(self):
        """Gating Phase 2: self.app is wired by the screen base already."""
        return self.app

    def _setup_window(self):
        """Setup the emergency screen (Tier-1: no Toplevel calls)."""
        self.configure(bg=self.DEADLINE_RED)
        # No grab_set, no topmost: a non-modal screen per Eastside grammar.

    def _create_interface(self):
        """Create emergency interface"""
        # Flash warning
        warning_frame = tk.Frame(self, bg=self.URGENT_RED, height=80)
        warning_frame.pack(fill='x')
        warning_frame.pack_propagate(False)

        tk.Label(warning_frame, text="EMERGENCY TRADE MODE",
                 bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 18, 'bold')).pack(expand=True)
        try:
            remaining = self.deadline_manager.get_time_until_deadline().get(
                'formatted', '')
        except Exception:
            remaining = ''
        tk.Label(warning_frame,
                 text=f"DEADLINE: {remaining}" if remaining else "DEADLINE DAY",
                 bg=self.URGENT_RED, fg='yellow',
                 font=('Segoe UI', 12, 'bold')).pack()

        # Quick options
        content = tk.Frame(self, bg=self.PANEL_COLOR)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        tk.Label(content, text="Emergency Options:",
                 bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
                 font=('Segoe UI', 14, 'bold')).pack(pady=(0, 12))

        self._emergency_option(
            content,
            "Fire Sale",
            "List every expiring contract on your roster on the trade "
            "block right now. Rival GMs can bid immediately.",
            self._fire_sale)

        # Status line: the real outcome of the last action.
        self._status_label = tk.Label(
            content, text="", bg=self.PANEL_COLOR, fg=self.TEXT_WHITE,
            font=('Segoe UI', 10), wraplength=520, justify='left')
        self._status_label.pack(fill='x', pady=(12, 0))

        tk.Label(content,
                 text="No extensions: the deadline cutoff is final.",
                 bg=self.PANEL_COLOR, fg='#9CA3AF',
                 font=('Segoe UI', 9, 'italic')).pack(pady=(10, 0))

        tk.Button(content, text="CLOSE", bg='#6B7280', fg=self.TEXT_WHITE,
                  font=('Segoe UI', 11, 'bold'), padx=24, pady=6,
                  command=self.close_view).pack(pady=(12, 0))

    def _emergency_option(self, parent, title, desc, command):
        option_frame = tk.Frame(parent, bg=self.PANEL_COLOR, relief='ridge',
                                bd=2)
        option_frame.pack(fill='x', pady=5)

        btn = tk.Button(option_frame, text=title,
                        bg=self.URGENT_RED, fg=self.TEXT_WHITE,
                        font=('Segoe UI', 11, 'bold'), command=command)
        btn.pack(fill='x', padx=5, pady=5)

        tk.Label(option_frame, text=desc,
                 bg=self.PANEL_COLOR, fg='#9CA3AF',
                 font=('Segoe UI', 9), wraplength=520,
                 justify='left').pack(padx=5, pady=(0, 5))

    def _set_status(self, text):
        self._status_label.config(text=text)

    def _fire_sale(self):
        """List your expiring contracts on the real trade block.

        Adds each expiring-contract player to the app's trade block (the
        store the Trade Block window reads) and mirrors them into the
        real trade_market listings (source 'user_block') so AI GMs bid.
        """
        import trade_market as tmk
        if self.app is None or self.user_team is None or \
                self.league is None:
            self._set_status("No league loaded -- nothing was listed.")
            return
        expiring = []
        for p in (getattr(self.user_team, 'roster', None) or []):
            try:
                if getattr(getattr(p, 'contract', None),
                           'years_remaining', 99) == 1:
                    expiring.append(p)
            except Exception:
                continue
        if not expiring:
            self._set_status("No expiring contracts on your roster -- "
                             "nothing to list.")
            return
        block = getattr(self.app, 'trade_block', None)
        if block is None:
            block = []
            self.app.trade_block = block
        listed, skipped = 0, 0
        for p in expiring:
            try:
                pid = getattr(p, 'id', None)
                if not any(getattr(e, 'id', None) == pid for e in block):
                    block.append(p)
                li = tmk.list_piece(self.app, self.league, self.user_team, p,
                                    source="user_block")
                if li is not None:
                    listed += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        try:
            update_views = getattr(self.app, 'update_all_views', None)
            if callable(update_views):
                update_views()
        except Exception:
            pass
        names = ", ".join(str(getattr(p, 'full_name', '?'))
                          for p in expiring[:4])
        if len(expiring) > 4:
            names += f" (+{len(expiring) - 4} more)"
        msg = (f"Fire sale: {listed} expiring contract(s) listed on the "
               f"trade block: {names}.")
        if skipped:
            msg += f" ({skipped} already listed or on cooldown.)"
        self._set_status(msg)


class DeadlineMarketBrowser(_DeadlineScreenBase):
    """Comprehensive market browser for deadline day trading"""

    def __init__(self, parent, deadline_manager, app=None):
        _DeadlineScreenBase.__init__(self, parent, app=app)
        self.deadline_manager = deadline_manager
        
        # Rumors from the media rumor engine (real league state), same as the
        # main center. (This also fixes a latent AttributeError: the rumors
        # section below read self.trade_rumors, which was never set here.)
        self.trade_rumors = media_rumors.generate_rumors(
            deadline_manager=self.deadline_manager)
        self._rumors_text = None

        # Colors: center-palette constants (the old code read them from the
        # center card; the frame background still comes from the app).
        self.BG_COLOR = (getattr(self.app, 'BG_COLOR', None)
                         or _DEADLINE_COLORS["DEADLINE_BG"])
        self.PANEL_COLOR = _DEADLINE_COLORS["PANEL_COLOR"]
        self.TEXT_WHITE = _DEADLINE_COLORS["TEXT_WHITE"]
        self.DEADLINE_GOLD = _DEADLINE_COLORS["DEADLINE_GOLD"]
        self.DEADLINE_RED = _DEADLINE_COLORS["DEADLINE_RED"]
        self.SUCCESS_GREEN = _DEADLINE_COLORS["SUCCESS_GREEN"]
        self.URGENT_RED = _DEADLINE_COLORS["URGENT_RED"]
        
        self._setup_window()
        self._create_interface()
        
    def _setup_window(self):
        """Setup market browser screen (Tier-1: no Toplevel calls)."""
        self.configure(bg=self.BG_COLOR)
        
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
        
        tk.Label(stats_frame, text="Market Statistics",
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
                 command=self.close_view,
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
        """Refresh market data: file a fresh batch of media rumors."""
        try:
            self.trade_rumors = media_rumors.generate_rumors(
                deadline_manager=self.deadline_manager, fresh=True)
            if self._rumors_text is not None:
                self._rumors_text.config(state='normal')
                self._rumors_text.delete('1.0', 'end')
                for rumor in self.trade_rumors:
                    self._rumors_text.insert('end', f"• {rumor}\n\n")
                self._rumors_text.config(state='disabled')
        except Exception as e:
            print(f"Rumor refresh failed: {e}")
        
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
        self._rumors_text = rumors_text  # for refresh without rebuilding
        
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
        
    def _create_deadline_status_footer(self, parent):
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
        if not self.winfo_exists():
            return  # Gating Phase 2: the view was destroyed on navigation
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
        if not self.winfo_exists():
            return  # Gating Phase 2: the view was destroyed on navigation
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
        if not self.winfo_exists():
            return  # Gating Phase 2: the view was destroyed on navigation
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

        if self.winfo_exists():
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

    def _close_deadline_center(self):
        """Close the trade deadline center"""
        self.auto_trades_active = False
        self.close_view()


def is_trade_deadline_day():
    """Check if today is trade deadline day (derived from the schedule)"""
    # Use the deadline manager for consistent logic
    manager = get_deadline_manager()
    return manager.is_trade_deadline_day()




if __name__ == "__main__":
    # Test the Trade Deadline Center
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    # Create and show trade deadline center
    deadline_center = TradeDeadlineCenter(root)
    
    root.mainloop()
