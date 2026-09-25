# sleeper_profile.py
# modern player profile.
# Clean, modern, no white text boxes.

import tkinter as tk
from tkinter import ttk
from sleeper_ui import (
    AppColors, AppFonts, AppCard, PillBadge, AppButton
)


class PlayerProfile(tk.Toplevel):
    """Modern player profile (modern).
    
    Layout:
    - Header: large avatar, name, position pills, team
    - Stat cards: key metrics in cards
    - Attributes: visual bars instead of text boxes
    - No white boxes, no Excel look
    """
    
    def __init__(self, parent, player, **kwargs):
        super().__init__(parent, **kwargs)
        self.player = player
        self.parent_app = parent
        
        # Window setup
        try:
            name = f"{player.first_name} {player.last_name}"
        except:
            name = "Player Profile"
        
        self.title(f"{name} - Profile")
        self.geometry("900x700")
        self.configure(bg=AppColors.BG)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the profile UI."""
        # Scrollable main
        canvas = tk.Canvas(self, bg=AppColors.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        main = tk.Frame(canvas, bg=AppColors.BG)
        
        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Content
        content = tk.Frame(main, bg=AppColors.BG)
        content.pack(fill="both", expand=True, padx=24, pady=24)
        
        self._create_header(content)
        self._create_stats(content)
        self._create_attributes(content)
    
    def _create_header(self, parent):
        """Player header with avatar and basic info."""
        header = tk.Frame(parent, bg=AppColors.BG)
        header.pack(fill="x", pady=(0, 24))
        
        # Large avatar
        size = 96
        avatar = tk.Canvas(header, width=size, height=size,
                          bg=AppColors.BG, highlightthickness=0)
        avatar.pack(side="left")
        
        # Position color
        try:
            pos = str(self.player.primary_position).upper()
            if 'GOALIE' in pos:
                color = AppColors.INFO
            elif 'DEFENSE' in pos:
                color = AppColors.WARNING
            else:
                color = AppColors.ACCENT
        except:
            color = AppColors.ACCENT
        
        avatar.create_oval(2, 2, size-2, size-2, fill=color, outline="")
        
        try:
            initials = f"{self.player.first_name[0]}{self.player.last_name[0]}".upper()
        except:
            initials = "?"
        avatar.create_text(size//2, size//2, text=initials,
                          font=("Segoe UI", 28, "bold"), fill="white")
        
        # Info
        info = tk.Frame(header, bg=AppColors.BG)
        info.pack(side="left", padx=20, fill="y")
        
        try:
            name = f"{self.player.first_name} {self.player.last_name}"
        except:
            name = "Unknown Player"
        
        name_label = tk.Label(info, text=name,
                             font=("Segoe UI", 24, "bold"),
                             fg=AppColors.TEXT_PRIMARY,
                             bg=AppColors.BG)
        name_label.pack(anchor="w")
        
        # Pills row
        pills = tk.Frame(info, bg=AppColors.BG)
        pills.pack(anchor="w", pady=(12, 0))
        
        try:
            pos_str = str(self.player.primary_position).split('.')[-1]
            pos_pill = PillBadge(pills, text=pos_str,
                                 bg=AppColors.ACCENT_BG,
                                 fg=AppColors.ACCENT)
            pos_pill.pack(side="left", padx=(0, 8))
            
            age = getattr(self.player, 'age', '?')
            age_pill = PillBadge(pills, text=f"Age {age}",
                                 bg=AppColors.BG_ELEVATED,
                                 fg=AppColors.TEXT_SECONDARY)
            age_pill.pack(side="left", padx=(0, 8))
            
            # Overall
            overall = getattr(self.player, 'overall', 0)
            if isinstance(overall, (int, float)) and overall < 30:
                try:
                    from game_classes import to_100_scale
                    overall = int(to_100_scale(overall))
                except:
                    overall = int(overall)
            ovr_pill = PillBadge(pills, text=f"{overall} OVR",
                                 bg=AppColors.BG_ELEVATED,
                                 fg=AppColors.TEXT_PRIMARY)
            ovr_pill.pack(side="left")
        except:
            pass
    
    def _create_stats(self, parent):
        """Season stats in cards."""
        card = AppCard(parent)
        card.pack(fill="x", pady=(0, 16))
        content = card.get_content_frame()
        
        title = tk.Label(content, text="Season Stats",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 16))
        
        # Stats grid
        stats_frame = tk.Frame(content, bg=card.card_bg)
        stats_frame.pack(fill="x")
        
        try:
            is_goalie = 'GOALIE' in str(self.player.primary_position).upper()
            stats = self.player.stats
            
            if is_goalie:
                items = [
                    ("GP", getattr(stats, 'games_played', 0)),
                    ("W", getattr(stats, 'wins', 0)),
                    ("SV%", f"{getattr(stats, 'save_percentage', 0):.3f}"),
                    ("GAA", f"{getattr(stats, 'goals_against_average', 0):.2f}"),
                ]
            else:
                items = [
                    ("GP", getattr(stats, 'games_played', 0)),
                    ("G", getattr(stats, 'goals', 0)),
                    ("A", getattr(stats, 'assists', 0)),
                    ("PTS", getattr(stats, 'points', 0)),
                ]
        except:
            items = [("GP", 0), ("G", 0), ("A", 0), ("PTS", 0)]
        
        for label, value in items:
            col = tk.Frame(stats_frame, bg=card.card_bg)
            col.pack(side="left", fill="both", expand=True)
            
            val_label = tk.Label(col, text=str(value),
                                font=AppFonts.STAT_SMALL,
                                fg=AppColors.TEXT_PRIMARY,
                                bg=card.card_bg)
            val_label.pack()
            
            lbl = tk.Label(col, text=label,
                          font=AppFonts.CAPTION,
                          fg=AppColors.TEXT_SECONDARY,
                          bg=card.card_bg)
            lbl.pack()
    
    def _create_attributes(self, parent):
        """Attributes with visual bars (no text boxes)."""
        card = AppCard(parent)
        card.pack(fill="x")
        content = card.get_content_frame()
        
        title = tk.Label(content, text="Attributes",
                        font=AppFonts.H2,
                        fg=AppColors.TEXT_PRIMARY,
                        bg=card.card_bg)
        title.pack(anchor="w", pady=(0, 16))
        
        # Key attributes with bars
        try:
            is_goalie = 'GOALIE' in str(self.player.primary_position).upper()
            if is_goalie:
                attrs = [
                    ("Positioning", getattr(self.player, 'positioning', 0)),
                    ("Reflexes", getattr(self.player, 'reflexes', 0)),
                    ("Rebound Control", getattr(self.player, 'rebound_control', 0)),
                ]
            else:
                attrs = [
                    ("Shooting", getattr(self.player, 'shooting', 0)),
                    ("Skating", getattr(self.player, 'skating', 0)),
                    ("Passing", getattr(self.player, 'passing', 0)),
                    ("Defense", getattr(self.player, 'defense', 0)),
                ]
        except:
            attrs = []
        
        for name, value in attrs:
            self._create_attribute_bar(content, name, value, card.card_bg)
    
    def _create_attribute_bar(self, parent, name, value, bg):
        """Create a visual attribute bar."""
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=6)
        
        # Name
        name_label = tk.Label(row, text=name,
                             font=AppFonts.SMALL,
                             fg=AppColors.TEXT_SECONDARY,
                             bg=bg, width=16, anchor="w")
        name_label.pack(side="left")
        
        # Bar background
        bar_bg = tk.Frame(row, bg=AppColors.BG, height=8)
        bar_bg.pack(side="left", fill="x", expand=True, padx=12)
        
        # Convert to 0-100 if needed
        try:
            if value < 30:
                from game_classes import to_100_scale
                pct = to_100_scale(value) / 100
            else:
                pct = min(value / 100, 1.0)
        except:
            pct = 0.5
        
        # Bar fill
        bar_fill = tk.Frame(bar_bg, bg=AppColors.ACCENT, height=8)
        bar_fill.place(relx=0, rely=0, relwidth=pct, relheight=1)
        
        # Value
        try:
            if value < 30:
                from game_classes import to_100_scale
                display_val = int(to_100_scale(value))
            else:
                display_val = int(value)
        except:
            display_val = 0
        
        val_label = tk.Label(row, text=str(display_val),
                            font=AppFonts.SMALL_BOLD,
                            fg=AppColors.TEXT_PRIMARY,
                            bg=bg, width=4, anchor="e")
        val_label.pack(side="right")
