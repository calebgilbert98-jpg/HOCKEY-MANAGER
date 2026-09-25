# sleeper_roster.py
# Sleeper-inspired card-based roster view.
# Replaces Excel-like tables with modern player cards.

import tkinter as tk
from tkinter import ttk
from sleeper_ui import (
    SleeperColors, SleeperFonts, SleeperCard, SleeperPlayerRow,
    SleeperPill, SleeperButton
)


class SleeperRosterView(tk.Frame):
    """Card-based roster view (Sleeper-style).
    
    Instead of a dense table, players are shown as clean cards
    with avatars, names, positions, and key stats.
    """
    
    def __init__(self, parent, players=None, on_player_click=None, **kwargs):
        super().__init__(parent, bg=SleeperColors.BG, **kwargs)
        
        self.players = players or []
        self.on_player_click = on_player_click
        self.position_filter = "All"
        
        self._create_ui()
        self.refresh()
    
    def _create_ui(self):
        """Create the roster UI."""
        # Header with position filter pills
        header = tk.Frame(self, bg=SleeperColors.BG)
        header.pack(fill="x", padx=16, pady=(16, 12))
        
        title = tk.Label(header, text="Roster",
                        font=SleeperFonts.H1,
                        fg=SleeperColors.TEXT_PRIMARY,
                        bg=SleeperColors.BG)
        title.pack(side="left")
        
        # Count badge
        self.count_label = tk.Label(header, text="",
                                   font=SleeperFonts.SMALL,
                                   fg=SleeperColors.TEXT_SECONDARY,
                                   bg=SleeperColors.BG)
        self.count_label.pack(side="left", padx=(12, 0))
        
        # Position filter pills
        filter_frame = tk.Frame(header, bg=SleeperColors.BG)
        filter_frame.pack(side="right")
        
        positions = ["All", "F", "D", "G"]
        self.filter_pills = {}
        for pos in positions:
            pill = tk.Frame(filter_frame, bg=SleeperColors.BG_ELEVATED,
                           cursor="hand2", padx=12, pady=6)
            pill.pack(side="left", padx=4)
            
            label = tk.Label(pill, text=pos,
                           font=SleeperFonts.SMALL_BOLD,
                           fg=SleeperColors.TEXT_SECONDARY,
                           bg=SleeperColors.BG_ELEVATED)
            label.pack()
            
            # Bind clicks
            for w in [pill, label]:
                w.bind("<Button-1>", lambda e, p=pos: self.set_filter(p))
            
            self.filter_pills[pos] = (pill, label)
        
        self._update_filter_ui()
        
        # Scrollable player list
        canvas = tk.Canvas(self, bg=SleeperColors.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=SleeperColors.BG)
        
        self.list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=16)
        scrollbar.pack(side="right", fill="y")
        
        # Group headers
        self.group_frames = {}
    
    def set_filter(self, position):
        """Set position filter."""
        self.position_filter = position
        self._update_filter_ui()
        self.refresh()
    
    def _update_filter_ui(self):
        """Update filter pill appearance."""
        for pos, (pill, label) in self.filter_pills.items():
            is_active = (pos == self.position_filter)
            bg = SleeperColors.ACCENT if is_active else SleeperColors.BG_ELEVATED
            fg = "#ffffff" if is_active else SleeperColors.TEXT_SECONDARY
            
            pill.configure(bg=bg)
            label.configure(bg=bg, fg=fg)
    
    def set_players(self, players):
        """Update the player list."""
        self.players = players
        self.refresh()
    
    def refresh(self):
        """Refresh the player list."""
        # Clear existing
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        # Filter players
        filtered = self._filter_players()
        
        # Update count
        self.count_label.configure(text=f"{len(filtered)} players")
        
        # Group by position
        groups = {"Forwards": [], "Defense": [], "Goalies": []}
        for p in filtered:
            pos = self._get_position_group(p)
            groups[pos].append(p)
        
        # Render groups
        for group_name, group_players in groups.items():
            if not group_players:
                continue
            
            # Group header
            header = tk.Label(self.list_frame,
                            text=group_name.upper(),
                            font=SleeperFonts.LABEL,
                            fg=SleeperColors.TEXT_SECONDARY,
                            bg=SleeperColors.BG)
            header.pack(anchor="w", pady=(16, 8), padx=4)
            
            # Player cards
            for player in group_players:
                card = self._create_player_card(player)
                card.pack(fill="x", pady=3)
    
    def _filter_players(self):
        """Filter players by position."""
        if self.position_filter == "All":
            return self.players
        
        filtered = []
        for p in self.players:
            pos = str(getattr(p, 'primary_position', '')).upper()
            if self.position_filter == "F" and any(x in pos for x in ['CENTER', 'WING', 'LEFT', 'RIGHT']):
                filtered.append(p)
            elif self.position_filter == "D" and 'DEFENSE' in pos:
                filtered.append(p)
            elif self.position_filter == "G" and 'GOALIE' in pos:
                filtered.append(p)
        
        return filtered
    
    def _get_position_group(self, player):
        """Get position group for a player."""
        pos = str(getattr(player, 'primary_position', '')).upper()
        if 'GOALIE' in pos:
            return "Goalies"
        elif 'DEFENSE' in pos:
            return "Defense"
        else:
            return "Forwards"
    
    def _create_player_card(self, player):
        """Create a Sleeper-style player card."""
        card = tk.Frame(self.list_frame, bg=SleeperColors.BG_ELEVATED,
                       highlightbackground=SleeperColors.BORDER,
                       highlightthickness=1,
                       cursor="hand2" if self.on_player_click else "")
        
        # Avatar
        avatar_size = 48
        avatar = tk.Canvas(card, width=avatar_size, height=avatar_size,
                          bg=SleeperColors.BG_ELEVATED, highlightthickness=0)
        avatar.pack(side="left", padx=12, pady=10)
        
        # Avatar color based on position
        pos = str(getattr(player, 'primary_position', '')).upper()
        if 'GOALIE' in pos:
            color = SleeperColors.INFO
        elif 'DEFENSE' in pos:
            color = SleeperColors.WARNING
        else:
            color = SleeperColors.ACCENT
        
        avatar.create_oval(2, 2, avatar_size-2, avatar_size-2,
                          fill=color, outline="")
        
        # Initials
        try:
            fn = getattr(player, 'first_name', '')
            ln = getattr(player, 'last_name', '')
            initials = f"{fn[0]}{ln[0]}".upper() if fn and ln else "?"
        except:
            initials = "?"
        
        avatar.create_text(avatar_size//2, avatar_size//2, text=initials,
                          font=("Segoe UI", 14, "bold"), fill="white")
        
        # Info
        info = tk.Frame(card, bg=SleeperColors.BG_ELEVATED)
        info.pack(side="left", fill="y", expand=True)
        
        # Name
        try:
            name = f"{getattr(player, 'first_name', '')} {getattr(player, 'last_name', '')}".strip()
            if not name:
                name = "Unknown Player"
        except:
            name = "Unknown Player"
        
        name_label = tk.Label(info, text=name,
                             font=SleeperFonts.BODY_BOLD,
                             fg=SleeperColors.TEXT_PRIMARY,
                             bg=SleeperColors.BG_ELEVATED,
                             anchor="w")
        name_label.pack(anchor="w", pady=(10, 0))
        
        # Details: position • age • overall
        try:
            pos_short = pos.split('.')[-1][:2] if '.' in pos else pos[:2]
            age = getattr(player, 'age', '?')
            overall = getattr(player, 'overall', '?')
            # Convert overall to 1-100 if needed
            if isinstance(overall, (int, float)) and overall < 30:
                # Likely internal scale, convert
                from game_classes import to_100_scale
                overall = to_100_scale(overall)
            detail_text = f"{pos_short} • Age {age} • {overall} OVR"
        except:
            detail_text = ""
        
        detail_label = tk.Label(info, text=detail_text,
                               font=SleeperFonts.SMALL,
                               fg=SleeperColors.TEXT_SECONDARY,
                               bg=SleeperColors.BG_ELEVATED,
                               anchor="w")
        detail_label.pack(anchor="w")
        
        # Stats (right side)
        stats_frame = tk.Frame(card, bg=SleeperColors.BG_ELEVATED)
        stats_frame.pack(side="right", padx=12)
        
        try:
            if 'GOALIE' in pos:
                # Goalie stats: SV%, GAA
                svp = getattr(player.stats, 'save_percentage', 0) if hasattr(player, 'stats') else 0
                gaa = getattr(player.stats, 'goals_against_average', 0) if hasattr(player, 'stats') else 0
                stat1_val, stat1_lbl = f"{svp:.3f}", "SV%"
                stat2_val, stat2_lbl = f"{gaa:.2f}", "GAA"
            else:
                # Skater stats: points, goals
                pts = getattr(player.stats, 'points', 0) if hasattr(player, 'stats') else 0
                goals = getattr(player.stats, 'goals', 0) if hasattr(player, 'stats') else 0
                stat1_val, stat1_lbl = str(pts), "PTS"
                stat2_val, stat2_lbl = str(goals), "G"
        except:
            stat1_val, stat1_lbl = "-", "PTS"
            stat2_val, stat2_lbl = "-", "G"
        
        # Stat 1
        s1_frame = tk.Frame(stats_frame, bg=SleeperColors.BG_ELEVATED)
        s1_frame.pack(side="left", padx=8)
        tk.Label(s1_frame, text=stat1_val,
                font=SleeperFonts.BODY_BOLD,
                fg=SleeperColors.TEXT_PRIMARY,
                bg=SleeperColors.BG_ELEVATED).pack(anchor="e")
        tk.Label(s1_frame, text=stat1_lbl,
                font=SleeperFonts.CAPTION,
                fg=SleeperColors.TEXT_TERTIARY,
                bg=SleeperColors.BG_ELEVATED).pack(anchor="e")
        
        # Stat 2
        s2_frame = tk.Frame(stats_frame, bg=SleeperColors.BG_ELEVATED)
        s2_frame.pack(side="left", padx=8)
        tk.Label(s2_frame, text=stat2_val,
                font=SleeperFonts.BODY_BOLD,
                fg=SleeperColors.TEXT_PRIMARY,
                bg=SleeperColors.BG_ELEVATED).pack(anchor="e")
        tk.Label(s2_frame, text=stat2_lbl,
                font=SleeperFonts.CAPTION,
                fg=SleeperColors.TEXT_TERTIARY,
                bg=SleeperColors.BG_ELEVATED).pack(anchor="e")
        
        # Click handler
        if self.on_player_click:
            for widget in [card, avatar, info, name_label, detail_label, stats_frame]:
                try:
                    widget.bind("<Button-1>", lambda e, p=player: self.on_player_click(p))
                except:
                    pass
        
        return card
