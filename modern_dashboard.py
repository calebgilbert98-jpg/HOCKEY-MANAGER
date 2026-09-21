# modern_dashboard.py
# Modern dashboard inspired by Football Manager and OOTP design principles

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from typing import Dict, List, Optional
import random

class ModernDashboard:
    """Modern dashboard with storytelling and visual hierarchy"""
    
    def __init__(self, parent, game_manager, theme):
        self.parent = parent
        self.game_manager = game_manager
        self.theme = theme
        self.user_team = game_manager.user_team
        
    def create_dashboard(self, container):
        """Create the modern dashboard layout that fills the entire window"""
        # Configure container to expand fully
        if hasattr(container, 'configure'):
            try:
                container.configure(bg=self.theme.colors.primary_bg)
            except:
                # If it's a ttk widget, skip background configuration
                pass
        
        # Create main frame that fills the entire container
        main_frame = ttk.Frame(container, style='TFrame')
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Configure grid weights for full expansion (without quick actions bar)
        main_frame.grid_rowconfigure(0, weight=0)    # Hero section - fixed height
        main_frame.grid_rowconfigure(1, weight=1)    # Main content - expandable
        main_frame.grid_rowconfigure(2, weight=0)    # News footer - fixed height
        main_frame.grid_columnconfigure(0, weight=1) # Full width
        
        # Create dashboard sections that use the full space
        self._create_hero_section(main_frame)
        # Removed quick actions bar - using enhanced menu bar instead
        self._create_main_content_grid(main_frame)
        self._create_news_and_updates(main_frame)
        
        return main_frame
    
    def _create_hero_section(self, parent):
        """Create the hero section with team branding and key info"""
        hero_frame = ttk.Frame(parent, style='Card.TFrame', padding=16)
        hero_frame.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        
        # Configure hero frame to expand horizontally
        parent.grid_columnconfigure(0, weight=1)
        hero_frame.grid_columnconfigure(1, weight=1)  # Middle section expands
        
        # Team logo and name (left side)
        team_info_frame = tk.Frame(hero_frame, bg=self.theme.colors.primary_bg)
        team_info_frame.grid(row=0, column=0, sticky='w', padx=(0, 20))
        
        # Team logo placeholder (colored circle)
        from team_identity_system import nhl_identity
        team_colors = nhl_identity.get_team_colors(self.user_team.team_name)
        primary_color = team_colors.primary if team_colors else self.theme.colors.primary_accent
        
        logo_frame = tk.Frame(team_info_frame, bg=primary_color, width=48, height=48)
        logo_frame.pack(side='left', padx=(0, 12))
        logo_frame.pack_propagate(False)
        
        # Team name and record
        team_text_frame = tk.Frame(team_info_frame, bg=self.theme.colors.primary_bg)
        team_text_frame.pack(side='left', fill='y')
        
        tk.Label(team_text_frame, text=self.user_team.team_name, 
                 font=('Segoe UI', 16, 'bold'), fg=self.theme.colors.primary_text, 
                 bg=self.theme.colors.primary_bg).pack(anchor='w')
        tk.Label(team_text_frame, text="Record: 0-0-0", 
                 font=('Segoe UI', 11), fg=self.theme.colors.secondary_text,
                 bg=self.theme.colors.primary_bg).pack(anchor='w')
        
        # Key metrics (center)
        metrics_frame = tk.Frame(hero_frame, bg=self.theme.colors.primary_bg)
        metrics_frame.grid(row=0, column=1, sticky='ew', padx=20)
        
        # Create 4 metric cards in a row
        metrics = [
            ("Next Game", "vs. TBD", "Tomorrow"),
            ("Salary Cap", "$82.5M", "Available"),
            ("Roster", "23/23", "Players"),
            ("Standing", "1st", "Atlantic")
        ]
        
        for i, (title, value, subtitle) in enumerate(metrics):
            metric_card = ttk.Frame(metrics_frame, style='Card.TFrame', padding=8)
            metric_card.grid(row=0, column=i, sticky='ew', padx=4)
            metrics_frame.grid_columnconfigure(i, weight=1)
            
            tk.Label(metric_card, text=title, font=('Segoe UI', 9), 
                     fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack()
            tk.Label(metric_card, text=value, font=('Segoe UI', 12, 'bold'), 
                     fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack()
            tk.Label(metric_card, text=subtitle, font=('Segoe UI', 8), 
                     fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack()
        
        # Date and continue button (right side)
        date_frame = tk.Frame(hero_frame, bg=self.theme.colors.primary_bg)
        date_frame.grid(row=0, column=2, sticky='e')
        
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        current_time = datetime.now().strftime("%I:%M %p")
        
        tk.Label(date_frame, text=current_date, font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.primary_bg).pack(anchor='e')
        tk.Label(date_frame, text=current_time, font=('Segoe UI', 9), 
                 fg=self.theme.colors.secondary_text, bg=self.theme.colors.primary_bg).pack(anchor='e')
        
        # Add Continue Day button
        continue_btn = tk.Button(date_frame, text="Continue Day", 
                               font=('Segoe UI', 10, 'bold'),
                               bg=self.theme.colors.primary_accent,
                               fg='white',
                               relief='flat',
                               bd=0,
                               padx=20,
                               pady=8,
                               cursor='hand2',
                               activebackground=getattr(self.theme.colors, 'danger', self.theme.colors.primary_accent),
                               activeforeground='white',
                               command=self._continue_action)
        continue_btn.pack(anchor='e', pady=(10, 0))
        
        # Add hover effects
        hover_color = getattr(self.theme.colors, 'warning', self.theme.colors.primary_accent)
        def on_enter(event):
            continue_btn.configure(bg=hover_color)
        def on_leave(event):
            continue_btn.configure(bg=self.theme.colors.primary_accent)
            
        continue_btn.bind("<Enter>", on_enter)
        continue_btn.bind("<Leave>", on_leave)
        
        # Store reference for enabling/disabling
        self.continue_btn = continue_btn
        
        # Team initials in logo
        initials = ''.join([word[0] for word in self.user_team.team_name.split()[:2]])
        logo_label = tk.Label(logo_frame, text=initials,
                             bg=primary_color,
                             fg='white',
                             font=('Segoe UI', 16, 'bold'))
        logo_label.place(relx=0.5, rely=0.5, anchor='center')
    
    def _create_quick_actions_bar(self, parent):
        """Create quick action buttons bar"""
        actions_frame = tk.Frame(parent, bg=self.theme.colors.primary_bg)
        actions_frame.grid(row=1, column=0, sticky='ew', padx=8, pady=8)
        
        # Configure for equal spacing
        for i in range(6):
            actions_frame.grid_columnconfigure(i, weight=1)
        
        # Quick action buttons
        actions = [
            ("Continue", "Next Day", self._continue_action),
            ("Roster", "Manage Team", self._roster_action),
            ("Trades", "Make Deals", self._trade_action),
            ("Free Agency", "Sign Players", self._free_agency_action),
            ("Schedule", "View Games", self._schedule_action),
            ("Stats", "Team Stats", self._stats_action)
        ]
        
        for i, (title, subtitle, command) in enumerate(actions):
            # Create styled button frame that looks professional
            btn_frame = tk.Frame(actions_frame, bg=self.theme.colors.secondary_bg, 
                               relief='raised', bd=1, cursor='hand2')
            btn_frame.grid(row=0, column=i, sticky='nsew', padx=3, pady=2)
            
            # Configure button frame to expand
            btn_frame.grid_rowconfigure(0, weight=1)
            btn_frame.grid_columnconfigure(0, weight=1)
            
            # Create internal frame for content
            content_frame = tk.Frame(btn_frame, bg=self.theme.colors.secondary_bg)
            content_frame.pack(fill='both', expand=True, padx=8, pady=6)
            
            # Button title
            title_label = tk.Label(content_frame, text=title, 
                                 bg=self.theme.colors.secondary_bg,
                                 fg=self.theme.colors.primary_text,
                                 font=('Segoe UI', 10, 'bold'))
            title_label.pack()
            
            # Button subtitle
            subtitle_label = tk.Label(content_frame, text=subtitle,
                                    bg=self.theme.colors.secondary_bg,
                                    fg=self.theme.colors.secondary_text,
                                    font=('Segoe UI', 8))
            subtitle_label.pack()
            
            # Bind click events to all components
            def make_click_handler(cmd):
                return lambda e: cmd()
            
            click_handler = make_click_handler(command)
            btn_frame.bind("<Button-1>", click_handler)
            content_frame.bind("<Button-1>", click_handler)
            title_label.bind("<Button-1>", click_handler)
            subtitle_label.bind("<Button-1>", click_handler)
            
            # Add hover effects
            def on_enter(e):
                btn_frame.configure(bg=self.theme.colors.primary_accent, relief='raised', bd=2)
                content_frame.configure(bg=self.theme.colors.primary_accent)
                title_label.configure(bg=self.theme.colors.primary_accent)
                subtitle_label.configure(bg=self.theme.colors.primary_accent)
            
            def on_leave(e):
                btn_frame.configure(bg=self.theme.colors.secondary_bg, relief='raised', bd=1)
                content_frame.configure(bg=self.theme.colors.secondary_bg)
                title_label.configure(bg=self.theme.colors.secondary_bg)
                subtitle_label.configure(bg=self.theme.colors.secondary_bg)
            
            btn_frame.bind("<Enter>", on_enter)
            btn_frame.bind("<Leave>", on_leave)
            content_frame.bind("<Enter>", on_enter)
            content_frame.bind("<Leave>", on_leave)
            title_label.bind("<Enter>", on_enter)
            title_label.bind("<Leave>", on_leave)
            subtitle_label.bind("<Enter>", on_enter)
            subtitle_label.bind("<Leave>", on_leave)
    
    def _create_main_content_grid(self, parent):
        """Create main content grid with key information and prominent inbox"""
        content_frame = ttk.Frame(parent, style='TFrame')
        content_frame.grid(row=1, column=0, sticky='nsew', padx=8, pady=4)
        
        # Configure grid for inbox taking more space
        content_frame.grid_columnconfigure(0, weight=2)  # Inbox column gets more space  
        content_frame.grid_columnconfigure(1, weight=1)  # Other content
        content_frame.grid_rowconfigure((0,1), weight=1)
        
        # Create prominent inbox section on the left
        self._create_prominent_inbox_section(content_frame, 0, 0, rowspan=2)
        
        # Create other content cards on the right
        self._create_team_stats_card(content_frame, 0, 1)
        self._create_recent_activity_card(content_frame, 1, 1)
        
    def _create_roster_overview_card(self, parent, row, col):
        """Create roster overview card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="ROSTER OVERVIEW", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        # Sample roster data
        roster_info = [
            ("Forwards", "12/12"),
            ("Defensemen", "6/6"),
            ("Goalies", "2/2"),
            ("Injured", "3"),
            ("Prospects", "15")
        ]
        
        for label, value in roster_info:
            row_frame = tk.Frame(card, bg=self.theme.colors.tertiary_bg)
            row_frame.pack(fill='x', pady=2)
            tk.Label(row_frame, text=label, font=('Segoe UI', 9), 
                     fg=self.theme.colors.secondary_text, bg=self.theme.colors.tertiary_bg).pack(side='left')
            tk.Label(row_frame, text=value, font=('Segoe UI', 9, 'bold'), 
                     fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(side='right')
    
    def _create_team_stats_card(self, parent, row, col):
        """Create team stats card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="TEAM STATS", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        # Sample stats
        stats = [
            ("Goals For", "0", "Per Game"),
            ("Goals Against", "0", "Per Game"),
            ("Power Play", "0%", "Success"),
            ("Penalty Kill", "0%", "Success"),
            ("Shot %", "0%", "Team")
        ]
        
        for label, value, context in stats:
            row_frame = tk.Frame(card, bg=self.theme.colors.tertiary_bg)
            row_frame.pack(fill='x', pady=2)
            tk.Label(row_frame, text=label, font=('Segoe UI', 9), 
                     fg=self.theme.colors.secondary_text, bg=self.theme.colors.tertiary_bg).pack(side='left')
            tk.Label(row_frame, text=value, font=('Segoe UI', 9, 'bold'), 
                     fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(side='right')
    
    def _create_next_games_card(self, parent, row, col):
        """Create upcoming games card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="NEXT GAMES", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        # Sample upcoming games
        games = [
            ("Oct 12", "vs Rangers", "7:30 PM"),
            ("Oct 15", "@ Bruins", "7:00 PM"),
            ("Oct 18", "vs Leafs", "7:30 PM")
        ]
        
        for date, opponent, time in games:
            game_frame = tk.Frame(card, bg=self.theme.colors.tertiary_bg)
            game_frame.pack(fill='x', pady=3)
            tk.Label(game_frame, text=date, font=('Segoe UI', 8), 
                     fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack(side='left')
            tk.Label(game_frame, text=opponent, font=('Segoe UI', 9, 'bold'), 
                     fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(side='left', padx=(8, 0))
            tk.Label(game_frame, text=time, font=('Segoe UI', 8), 
                     fg=self.theme.colors.secondary_text, bg=self.theme.colors.tertiary_bg).pack(side='right')
    
    def _create_recent_activity_card(self, parent, row, col):
        """Create recent activity card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="RECENT ACTIVITY", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        tk.Label(card, text="No recent activity", font=('Segoe UI', 9), 
                 fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w')
    
    def _create_standings_card(self, parent, row, col):
        """Create standings card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="DIVISION STANDINGS", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        # Sample standings
        teams = [
            ("1. Team Name", "0-0-0", "0 PTS"),
            ("2. Team Name", "0-0-0", "0 PTS"),
            ("3. Team Name", "0-0-0", "0 PTS")
        ]
        
        for team, record, points in teams:
            team_frame = tk.Frame(card, bg=self.theme.colors.tertiary_bg)
            team_frame.pack(fill='x', pady=1)
            tk.Label(team_frame, text=team, font=('Segoe UI', 9), 
                     fg=self.theme.colors.secondary_text, bg=self.theme.colors.tertiary_bg).pack(side='left')
            tk.Label(team_frame, text=points, font=('Segoe UI', 9, 'bold'), 
                     fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(side='right')
    
    def _create_transactions_card(self, parent, row, col):
        """Create transactions card"""
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        
        tk.Label(card, text="RECENT TRANSACTIONS", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        tk.Label(card, text="No recent transactions", font=('Segoe UI', 9), 
                 fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w')
        
    def _create_news_and_updates(self, parent):
        """Create news and updates footer"""
        news_frame = ttk.Frame(parent, style='Card.TFrame', padding=12)
        news_frame.grid(row=2, column=0, sticky='ew', padx=8, pady=4)
        
        tk.Label(news_frame, text="LEAGUE NEWS", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w', pady=(0, 8))
        
        tk.Label(news_frame, text="Welcome to Hockey Manager! Begin your management career.", 
                 font=('Segoe UI', 9), fg=self.theme.colors.secondary_text, bg=self.theme.colors.tertiary_bg).pack(anchor='w')
    
    def _create_prominent_inbox_section(self, parent, row, col, rowspan=1):
        """Create a prominent inbox section that shows unread messages and urgent items"""
        inbox_card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        inbox_card.grid(row=row, column=col, rowspan=rowspan, sticky='nsew', padx=4, pady=4)
        
        # Header with inbox title and unread count
        header_frame = tk.Frame(inbox_card, bg=self.theme.colors.tertiary_bg)
        header_frame.pack(fill='x', pady=(0, 8))
        
        tk.Label(header_frame, text="📧 INBOX", font=('Segoe UI', 11, 'bold'), 
                 fg=self.theme.colors.primary_text, bg=self.theme.colors.tertiary_bg).pack(side='left')
        
        # Get unread count from inbox
        unread_count = 0
        if hasattr(self.parent, 'user_team') and hasattr(self.parent.user_team, 'inbox'):
            unread_count = self.parent.user_team.inbox.unread_count
        
        if unread_count > 0:
            unread_label = tk.Label(header_frame, text=f"{unread_count} unread", 
                                   font=('Segoe UI', 9, 'bold'), 
                                   fg=self.theme.colors.warning, bg=self.theme.colors.tertiary_bg)
            unread_label.pack(side='right')
        
        # Quick action to open full inbox
        open_inbox_btn = tk.Button(header_frame, text="Open Full Inbox", 
                                  font=('Segoe UI', 8), 
                                  bg=self.theme.colors.primary_accent, 
                                  fg=self.theme.colors.primary_text,
                                  relief='flat', cursor='hand2',
                                  command=self._open_inbox_action)
        open_inbox_btn.pack(side='right', padx=(10, 0))
        
        # Create scrollable message list
        messages_frame = tk.Frame(inbox_card, bg=self.theme.colors.tertiary_bg)
        messages_frame.pack(fill='both', expand=True)
        
        # Message list with scrollbar
        list_frame = tk.Frame(messages_frame, bg=self.theme.colors.tertiary_bg)
        list_frame.pack(fill='both', expand=True)
        
        # Canvas for scrolling
        canvas = tk.Canvas(list_frame, bg=self.theme.colors.tertiary_bg, highlightthickness=0, height=200)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.theme.colors.tertiary_bg)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate with recent messages (max 10)
        self._populate_inbox_preview(scrollable_frame)
        
        # Action buttons at bottom
        action_frame = tk.Frame(inbox_card, bg=self.theme.colors.tertiary_bg)
        action_frame.pack(fill='x', pady=(8, 0))
        
        tk.Button(action_frame, text="Mark All Read", 
                 font=('Segoe UI', 8), 
                 bg=self.theme.colors.secondary_bg, 
                 fg=self.theme.colors.primary_text,
                 relief='flat', cursor='hand2',
                 command=self._mark_all_read_action).pack(side='left', padx=(0, 5))
        
        tk.Button(action_frame, text="Compose", 
                 font=('Segoe UI', 8), 
                 bg=self.theme.colors.secondary_bg, 
                 fg=self.theme.colors.primary_text,
                 relief='flat', cursor='hand2',
                 command=self._compose_action).pack(side='left')
    
    def _populate_inbox_preview(self, parent):
        """Populate the inbox preview with recent messages"""
        if not hasattr(self.parent, 'user_team') or not hasattr(self.parent.user_team, 'inbox'):
            # No inbox yet, show placeholder
            tk.Label(parent, text="No messages yet", 
                    font=('Segoe UI', 9), 
                    fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack(pady=10)
            return
        
        inbox = self.parent.user_team.inbox
        recent_messages = inbox.messages[:10]  # Show latest 10 messages
        
        if not recent_messages:
            tk.Label(parent, text="No messages yet", 
                    font=('Segoe UI', 9), 
                    fg=self.theme.colors.muted_text, bg=self.theme.colors.tertiary_bg).pack(pady=10)
            return
        
        for message in recent_messages:
            self._create_message_preview_item(parent, message)
    
    def _create_message_preview_item(self, parent, message):
        """Create a preview item for a single message"""
        # Message container
        msg_frame = tk.Frame(parent, bg=self.theme.colors.secondary_bg, relief='solid', bd=1)
        msg_frame.pack(fill='x', pady=2, padx=2)
        
        # Make clickable
        msg_frame.bind("<Button-1>", lambda e: self._open_message_action(message))
        
        # Message header
        header_frame = tk.Frame(msg_frame, bg=self.theme.colors.secondary_bg)
        header_frame.pack(fill='x', padx=8, pady=4)
        
        # Priority indicator and read status
        indicator_text = ""
        text_color = self.theme.colors.primary_text
        
        if not message.is_read:
            indicator_text = "● "  # Unread indicator
            text_color = self.theme.colors.primary_text
        
        if message.is_urgent:
            indicator_text += "🔴 "
        elif message.is_important:
            indicator_text += "🟡 "
        
        # Sender and subject
        sender_text = f"{indicator_text}{message.sender}"
        tk.Label(header_frame, text=sender_text, 
                font=('Segoe UI', 8, 'bold' if not message.is_read else 'normal'), 
                fg=text_color, bg=self.theme.colors.secondary_bg).pack(side='left')
        
        # Date
        date_str = message.date_sent.strftime("%m/%d")
        if message.get_age_days() == 0:
            date_str = "Today"
        elif message.get_age_days() == 1:
            date_str = "Yesterday"
        
        tk.Label(header_frame, text=date_str, 
                font=('Segoe UI', 7), 
                fg=self.theme.colors.muted_text, bg=self.theme.colors.secondary_bg).pack(side='right')
        
        # Subject line (truncated)
        subject_text = message.subject[:40] + "..." if len(message.subject) > 40 else message.subject
        tk.Label(msg_frame, text=subject_text, 
                font=('Segoe UI', 8), 
                fg=self.theme.colors.secondary_text, bg=self.theme.colors.secondary_bg).pack(anchor='w', padx=8, pady=(0, 4))
        
        # Make all child widgets clickable too
        for widget in msg_frame.winfo_children():
            widget.bind("<Button-1>", lambda e: self._open_message_action(message))
            for child in widget.winfo_children():
                child.bind("<Button-1>", lambda e: self._open_message_action(message))
    
    def _open_inbox_action(self):
        """Open the full inbox window"""
        if hasattr(self.parent, 'open_inbox_window'):
            self.parent.open_inbox_window()
    
    def _open_message_action(self, message):
        """Open a specific message in the inbox"""
        if hasattr(self.parent, 'open_inbox_window'):
            self.parent.open_inbox_window()
            # TODO: Select the specific message in the inbox
    
    def _mark_all_read_action(self):
        """Mark all messages as read"""
        if hasattr(self.parent, 'user_team') and hasattr(self.parent.user_team, 'inbox'):
            self.parent.user_team.inbox.mark_all_read()
            # Refresh the dashboard
            if hasattr(self.parent, 'update_dashboard_data'):
                self.parent.update_dashboard_data()
    
    def _compose_action(self):
        """Open compose window"""
        # For now, show info message
        print("Compose functionality coming soon!")
        
    # Action methods
    def _continue_action(self):
        """Handle continue action"""
        if hasattr(self.parent, 'simulate_day'):
            self.parent.simulate_day()
    
    def _roster_action(self):
        """Handle roster action"""
        if hasattr(self.parent, 'open_roster_window'):
            self.parent.open_roster_window()
    
    def _trade_action(self):
        """Handle trade action"""
        if hasattr(self.parent, 'open_trade_window'):
            self.parent.open_trade_window()
    
    def _free_agency_action(self):
        """Handle free agency action"""
        if hasattr(self.parent, 'open_free_agency_window'):
            self.parent.open_free_agency_window()
    
    def _schedule_action(self):
        """Handle schedule action"""
        if hasattr(self.parent, 'open_schedule_window'):
            self.parent.open_schedule_window()
    
    def _stats_action(self):
        """Handle stats action"""
        # Would open stats window
        pass
    
    def update_data(self, current_date=None, team_record=None, next_game=None, 
                   roster_highlights=None, recent_news=None):
        """Update dashboard with current game data"""
        # Store data for future updates
        if current_date:
            self.current_date = current_date
        if team_record:
            self.team_record = team_record
        if next_game:
            self.next_game = next_game
        if roster_highlights:
            self.roster_highlights = roster_highlights
        if recent_news:
            self.recent_news = recent_news
        
        # TODO: Update dashboard widgets with new data
        # This would update labels, refresh stats, etc.
        print(f"Dashboard updated: {current_date}, Record: {team_record}")
