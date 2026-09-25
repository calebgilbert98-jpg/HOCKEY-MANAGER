# sleeper_dashboard.py
# modern dashboard for Puck Dynasty.
# Clean, modern, card-based UI with generous whitespace.

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from sleeper_ui import (
    AppColors, AppFonts, AppCard, StatCard,
    PlayerRow, PillBadge, AppButton, apply_app_theme
)


class HomeDashboard:
    """Modern, modern dashboard."""
    
    def __init__(self, parent, game_manager, user_team, on_continue=None):
        self.parent = parent
        self.game_manager = game_manager
        self.user_team = user_team
        self.on_continue = on_continue
        self.widgets = {}
    
    def create_dashboard(self, container):
        """Create the modern dashboard."""
        # Clear container
        for widget in container.winfo_children():
            widget.destroy()
        
        # Main background
        main = tk.Frame(container, bg=AppColors.BG)
        main.pack(fill="both", expand=True)
        
        # Scrollable content
        canvas = tk.Canvas(main, bg=AppColors.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=AppColors.BG)
        
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Content with max width (centered with max width)
        content = tk.Frame(scrollable, bg=AppColors.BG)
        content.pack(fill="both", expand=True, padx=24, pady=24)
        
        # Build sections
        self._create_header(content)
        self._create_stat_cards(content)
        self._create_main_grid(content)
        
        return main
    
    def _create_header(self, parent):
        """Team header with avatar and record."""
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 24))
        
        # Team avatar (large circle)
        avatar_size = 72
        avatar = tk.Canvas(header, width=avatar_size, height=avatar_size,
                          bg=AppColors.BG, highlightthickness=0)
        avatar.pack(side="left")
        
        # Team color (use accent or team color)
        team_color = getattr(self.user_team, 'primary_color', AppColors.ACCENT)
        if team_color in ['#FFFFFF', '#ffffff', 'white']:
            team_color = AppColors.ACCENT
        
        avatar.create_oval(2, 2, avatar_size-2, avatar_size-2,
                          fill=team_color, outline="")
        
        # Team initials
        name = self.user_team.team_name if hasattr(self.user_team, 'team_name') else "Team"
        initials = "".join([w[0] for w in name.split()[:2]]).upper()
        avatar.create_text(avatar_size//2, avatar_size//2, text=initials,
                          font=("Segoe UI", 20, "bold"), fill="white")
        
        # Team info
        info = tk.Frame(header, bg=AppColors.BG)
        info.pack(side="left", padx=16)
        
        name_label = tk.Label(info, text=name,
                             font=AppFonts.H1,
                             fg=AppColors.TEXT_PRIMARY,
                             bg=AppColors.BG)
        name_label.pack(anchor="w")
        
        # Record with pill
        record_frame = tk.Frame(info, bg=AppColors.BG)
        record_frame.pack(anchor="w", pady=(8, 0))
        
        # Get record
        try:
            wins = getattr(self.user_team, 'wins', 0)
            losses = getattr(self.user_team, 'losses', 0)
            otl = getattr(self.user_team, 'otl', 0)
            record_text = f"{wins}-{losses}-{otl}"
        except:
            record_text = "0-0-0"
        
        record_pill = PillBadge(record_frame, text=record_text,
                                 bg=AppColors.BG_ELEVATED,
                                 fg=AppColors.TEXT_PRIMARY)
        record_pill.pack(side="left")
        
        # Date (right side)
        date_frame = tk.Frame(header, bg=AppColors.BG)
        date_frame.pack(side="right")
        
        try:
            current_date = self.game_manager.current_date if hasattr(self.game_manager, 'current_date') else datetime.now().date()
            date_str = current_date.strftime("%B %d, %Y")
            day_str = current_date.strftime("%A")
        except:
            date_str = datetime.now().strftime("%B %d, %Y")
            day_str = datetime.now().strftime("%A")
        
        date_label = tk.Label(date_frame, text=date_str,
                             font=AppFonts.BODY_BOLD,
                             fg=AppColors.TEXT_PRIMARY,
                             bg=AppColors.BG)
        date_label.pack(anchor="e")
        
        day_label = tk.Label(date_frame, text=day_str,
                            font=AppFonts.SMALL,
                            fg=AppColors.ACCENT,
                            bg=AppColors.BG)
        day_label.pack(anchor="e")
        
        # Continue button
        continue_btn = AppButton(
            date_frame, text="Continue",
            command=self._on_continue,
            style="primary", width=140, height=40
        )
        continue_btn.pack(pady=(12, 0))
    
    def _create_stat_cards(self, parent):
        """Row of stat cards (modern)."""
        cards_frame = tk.Frame(parent, bg=AppColors.BG)
        cards_frame.pack(fill="x", pady=(0, 24))
        
        # Get stats
        try:
            wins = getattr(self.user_team, 'wins', 0)
            points = getattr(self.user_team, 'points', 0)
            gf = getattr(self.user_team, 'goals_for', 0)
            gp = getattr(self.user_team, 'games_played', 1)
            gpg = gf / max(gp, 1)
        except:
            wins, points, gpg = 0, 0, 0.0
        
        stats = [
            ("Wins", str(wins), "Season", AppColors.TEXT_PRIMARY),
            ("Points", str(points), "Standings", AppColors.ACCENT),
            ("Goals/Game", f"{gpg:.1f}", "Offense", AppColors.TEXT_PRIMARY),
        ]
        
        for i, (label, value, caption, color) in enumerate(stats):
            card = StatCard(
                cards_frame,
                value=value,
                label=label,
                caption=caption,
                value_color=color,
                accent_top=(i == 1)  # Highlight middle card
            )
            card.pack(side="left", fill="both", expand=True,
                     padx=(0, 12) if i < 2 else (0, 0))
    
    def _create_main_grid(self, parent):
        """Two-column grid: main content + sidebar."""
        grid = tk.Frame(parent, bg=AppColors.BG)
        grid.pack(fill="both", expand=True)
        
        # Left column (2/3 width)
        left = tk.Frame(grid, bg=AppColors.BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        
        # Right column (1/3 width)
        right = tk.Frame(grid, bg=AppColors.BG)
        right.pack(side="right", fill="both", expand=True, padx=(12, 0))
        
        self._create_team_section(left)
        self._create_next_game_card(right)
        self._create_inbox_card(right)
    
    def _create_team_section(self, parent):
        """Top players section."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        
        # Title
        title = tk.Label(content, text="Top Performers",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 12))
        
        # Get top players (simplified)
        try:
            players = []
            if hasattr(self.user_team, 'roster'):
                # Sort by points (simplified)
                skaters = [p for p in self.user_team.roster 
                          if hasattr(p, 'primary_position') and 'GOALIE' not in str(p.primary_position)]
                # Get top 3 by a simple metric
                for p in skaters[:3]:
                    name = f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip() or "Player"
                    pos = str(getattr(p, 'primary_position', '')).split('.')[-1][:2]
                    try:
                        pts = p.stats.points if hasattr(p.stats, 'points') else 0
                    except:
                        pts = 0
                    players.append((name, pos, str(pts), "PTS"))
        except:
            players = []
        
        if not players:
            players = [("No players", "", "", "")]
        
        for name, pos, stat_val, stat_label in players[:5]:
            row = PlayerRow(
                content,
                name=name,
                position=pos,
                stat_value=stat_val,
                stat_label=stat_label,
                bg=card.card_bg
            )
            row.pack(fill="x", pady=2)
    
    def _create_next_game_card(self, parent):
        """Next game card."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        
        title = tk.Label(content, text="Next Game",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 12))
        
        # Opponent info (simplified)
        opp_label = tk.Label(content, text="vs. Opponent",
                            font=AppFonts.BODY_BOLD,
                            fg=AppColors.ACCENT,
                            bg=card.card_bg)
        opp_label.pack(anchor="w")
        
        date_label = tk.Label(content, text="Upcoming",
                             font=AppFonts.SMALL,
                             fg=AppColors.TEXT_SECONDARY,
                             bg=card.card_bg)
        date_label.pack(anchor="w", pady=(4, 0))
    
    def _create_inbox_card(self, parent):
        """Inbox preview card."""
        card = AppCard(parent)
        card.pack(fill="x")
        content = card.get_content_frame()
        
        # Header with count
        header = tk.Frame(content, bg=card.card_bg)
        header.pack(fill="x", pady=(0, 12))
        
        title = tk.Label(header, text="Inbox",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(side="left")
        
        # Unread pill
        try:
            unread = 3  # Simplified
        except:
            unread = 0
        
        if unread > 0:
            pill = PillBadge(header, text=f"{unread} new",
                              bg=AppColors.DANGER,
                              fg="#ffffff")
            pill.pack(side="right")
        
        # Messages (simplified)
        messages = [
            "Season Preview",
            "Welcome Message",
        ]
        
        for msg in messages:
            msg_frame = tk.Frame(content, bg=AppColors.BG,
                                highlightbackground=AppColors.BORDER,
                                highlightthickness=1)
            msg_frame.pack(fill="x", pady=4)
            
            msg_label = tk.Label(msg_frame, text=msg,
                                font=AppFonts.SMALL,
                                fg=AppColors.TEXT_PRIMARY,
                                bg=AppColors.BG,
                                padx=12, pady=8)
            msg_label.pack(anchor="w")
    
    def _on_continue(self):
        """Handle continue button."""
        if self.on_continue:
            self.on_continue()
        else:
            print("Continue clicked (no handler)")
    
    def update_data(self, current_date=None, team_record=None, 
                   next_game=None, roster_highlights=None, recent_news=None):
        """Refresh dashboard data.
        
        Accepts the same kwargs as AtmosphericDashboard for compatibility.
        Currently the dashboard reads live from game_manager/user_team,
        so this is a no-op placeholder for future refresh logic.
        """
        # TODO: Implement live refresh without full rebuild
        # For now, data is read at creation time from game_manager/user_team
        pass
