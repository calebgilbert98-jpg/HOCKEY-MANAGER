# ui_components.py
# Contains reusable UI elements, like the player profile window.

import tkinter as tk
from popup_system import InGamePopup
from tkinter import ttk
import customtkinter as ctk
from game_classes import PlayerPosition, to_100_scale

def _to_20_scale(value, default=10):
    """Convert a 50-point-scale attribute to the 1-20 display scale."""
    try:
        return max(1, min(20, round(float(value) * 0.4)))
    except Exception:
        return default


def _to_100_scale(value):
    """Attributes are native 1-100 since the 100-scale conversion.

    The old converter doubled values < 55, which corrupts legitimate
    native sub-55 attributes. Display clamps the native value instead.
    """
    try:
        return max(1, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 50


class PlayerProfileView(ctk.CTkFrame):
    """A comprehensive player profile view similar to Eastside Hockey Manager.

    A plain CTkFrame so it can be embedded anywhere: full-screen inside the
    main window (the default, via HockeyManagerGUI.show_screen) or inside
    the legacy PlayerProfileWindow popup card.
    """
    def __init__(self, parent, player, is_scouted=False, report=None, app=None):
        self.app = app if app is not None else parent
        ctk.CTkFrame.__init__(self, parent, fg_color=self.app.BG_COLOR)
        # Set by show_screen() (dashboard) or the PlayerProfileWindow wrapper (card).
        self._close_screen = None
        self.player = player
        self.is_scouted = is_scouted
        self.report = report

        self.style = self.app.style
        self._setup_local_styles()
        
        # Create notebook for tabs with zero padding to maximize space
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=0, pady=0)
        
        # Create tabs
        self._create_overview_tab()
        self._create_attributes_tab()
        self._create_personality_tab()
        self._create_stats_tab()
        self._create_contract_tab()
        self._create_development_tab()

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _setup_local_styles(self):
        """Adds styles specific to this window."""
        self.style.configure('PlayerTab.TFrame', background=self.app.CONTENT_BG)
        self.style.configure('PlayerPanel.TFrame', background=self.app.CONTENT_BG, borderwidth=0)
        
        self.style.configure('PlayerHeader.TLabel', 
                           background=self.app.CONTENT_BG, 
                           foreground=self.app.HEADER_COLOR, 
                           font=(self.app.FONT_FAMILY, 24, 'bold'))  # Increased from 16 to 24
        
        self.style.configure('PlayerSubheader.TLabel', 
                           background=self.app.CONTENT_BG, 
                           foreground=self.app.HEADER_COLOR, 
                           font=(self.app.FONT_FAMILY, 13, 'bold'))
        
        self.style.configure('PlayerInfo.TLabel', 
                           background=self.app.CONTENT_BG, 
                           foreground=self.app.TEXT_COLOR, 
                           font=(self.app.FONT_FAMILY, 14))  # Increased from 10 to 14
        
        self.style.configure('PlayerValue.TLabel', 
                           background=self.app.CONTENT_BG, 
                           foreground=self.app.HEADER_COLOR, 
                           font=(self.app.FONT_FAMILY, 14, 'bold'))  # Increased from 10 to 14
        
        # Attribute rating styles - increased font sizes for better readability
        self.style.configure('Excellent.TLabel', background="#4CAF50", foreground='white', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13
        self.style.configure('VeryGood.TLabel', background="#8BC34A", foreground='white', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13
        self.style.configure('Good.TLabel', background="#CDDC39", foreground='black', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13
        self.style.configure('Average.TLabel', background="#FFC107", foreground='black', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13
        self.style.configure('BelowAverage.TLabel', background="#FF9800", foreground='black', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13
        self.style.configure('Poor.TLabel', background="#F44336", foreground='white', font=(self.app.FONT_FAMILY, 13, 'bold'))  # Increased from 9 to 13

    def _get_attribute_style_and_text(self, value):
        """Returns a style name and descriptive text based on the attribute value (native 1-100)."""
        disp = _to_100_scale(value)
        if value >= 85:
            return "Excellent.TLabel", f"{disp} (Excellent)"
        elif value >= 75:
            return "VeryGood.TLabel", f"{disp} (Very Good)"
        elif value >= 65:
            return "Good.TLabel", f"{disp} (Good)"
        elif value >= 55:
            return "Average.TLabel", f"{disp} (Average)"
        elif value >= 40:
            return "BelowAverage.TLabel", f"{disp} (Below Avg)"
        else:
            return "Poor.TLabel", f"{disp} (Poor)"

    def _get_morale_style_and_text(self, value):
        """Morale runs 1-10 internally; display it on the 1-100 scale."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 5.0
        disp = max(1, min(100, int(round(v * 10))))
        if v >= 8.5:
            return "Excellent.TLabel", f"{disp} (Excellent)"
        elif v >= 7:
            return "VeryGood.TLabel", f"{disp} (Very Good)"
        elif v >= 5.5:
            return "Good.TLabel", f"{disp} (Good)"
        elif v >= 4:
            return "Average.TLabel", f"{disp} (Average)"
        elif v >= 2.5:
            return "BelowAverage.TLabel", f"{disp} (Below Avg)"
        else:
            return "Poor.TLabel", f"{disp} (Poor)"

    def _create_overview_tab(self):
        """Creates the main overview tab with comprehensive player information."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text='Overview')
        
        # Main container with scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Bind canvas width changes to update scrollable frame width
        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create main content in a three-column layout for better space utilization
        main_container = ttk.Frame(scrollable_frame, style='PlayerTab.TFrame')
        main_container.pack(fill='both', expand=True, padx=2, pady=5)
        main_container.grid_columnconfigure(0, weight=1, minsize=250)
        main_container.grid_columnconfigure(1, weight=1, minsize=250)
        main_container.grid_columnconfigure(2, weight=1, minsize=250)
        main_container.grid_rowconfigure(1, weight=1)  # Make content row expandable
        
        # Player Header - spans full width
        self._create_enhanced_player_header(main_container)
        
        # Three-column layout for comprehensive information display
        left_column = ttk.Frame(main_container, style='PlayerTab.TFrame')
        left_column.grid(row=1, column=0, sticky='nsew', padx=(0, 1))
        left_column.grid_columnconfigure(0, weight=1)
        for i in range(5):
            left_column.grid_rowconfigure(i, weight=1)
        
        center_column = ttk.Frame(main_container, style='PlayerTab.TFrame') 
        center_column.grid(row=1, column=1, sticky='nsew', padx=(1, 1))
        center_column.grid_columnconfigure(0, weight=1)
        for i in range(3):
            center_column.grid_rowconfigure(i, weight=1)
            
        right_column = ttk.Frame(main_container, style='PlayerTab.TFrame')
        right_column.grid(row=1, column=2, sticky='nsew', padx=(1, 0))
        right_column.grid_columnconfigure(0, weight=1)
        for i in range(7):  # Increased for additional content
            right_column.grid_rowconfigure(i, weight=1)
        
        # Left column content - Health, career & room
        # (Personal details moved to the Personality tab.)
        self._create_injury_history(left_column, 0)
        self._create_career_progression(left_column, 1)
        self._create_accolades(left_column, 2)
        self._create_career_moments(left_column, 4)
        self._create_team_chemistry(left_column, 3)
        
        # Center column content - Player Attributes (all attributes bucketed together)
        self._create_enhanced_key_attributes(center_column, 0)
        self._create_physical_attributes(center_column, 1)
        self._create_skill_development(center_column, 2)
        
        # Right column content - Contract, Performance & Management
        self._create_performance_metrics(right_column, 0)
        self._create_enhanced_contract_info(right_column, 1)
        self._create_market_value_info(right_column, 2)
        self._create_scouting_report(right_column, 3)
        self._create_coaching_notes(right_column, 4)
        
        # Add additional right column content to better utilize space
        self._create_simple_comparison(right_column, 5)
        self._create_league_standing(right_column, 6)

    def _create_enhanced_player_header(self, parent):
        """Creates an enhanced player header with comprehensive information."""
        header_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        header_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 5))
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_columnconfigure(2, weight=0)
        header_frame.grid_columnconfigure(3, weight=0)
        
        # Photo section - generated cartoon face
        photo_frame = ttk.Frame(header_frame, style='PlayerPanel.TFrame', padding=5)
        photo_frame.grid(row=0, column=0, rowspan=3, sticky='nw', padx=(0, 15))

        try:
            from player_faces import get_face_photo
            face_img = get_face_photo(self.player, size=120)
        except Exception:
            face_img = None
        if face_img is not None:
            self._face_img = face_img  # keep a reference
            photo_label = tk.Label(photo_frame, image=face_img,
                                   bg=self.app.CONTENT_BG,
                                   highlightthickness=2,
                                   highlightbackground=self.app.ACCENT_COLOR)
            photo_label.pack()
        else:
            photo_canvas = tk.Canvas(photo_frame, width=120, height=150, bg=self.app.TITLE_BAR_COLOR, highlightthickness=2, highlightcolor=self.app.ACCENT_COLOR)
            photo_canvas.pack()
            photo_canvas.create_text(60, 75, text="PLAYER\nPHOTO", fill=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 14, 'bold'), justify='center')
        
        # Main player information
        info_frame = ttk.Frame(header_frame, style='PlayerTab.TFrame')
        info_frame.grid(row=0, column=1, sticky='ew', pady=(5, 0))
        
        # Name and jersey with team colors
        name_frame = ttk.Frame(info_frame, style='PlayerTab.TFrame')
        name_frame.pack(fill='x', pady=(0, 5))
        
        name_text = f"#{self.player.jersey_number} {self.player.full_name}"
        ttk.Label(name_frame, text=name_text, style='PlayerHeader.TLabel').pack(side='left')
        
        # Position and handedness with color coding
        position_text = f"{self.player.primary_position.value}"
        if hasattr(self.player, 'secondary_position') and self.player.secondary_position:
            position_text += f"/{self.player.secondary_position.value}"
        
        position_label = ttk.Label(name_frame, text=position_text, style='PlayerSubheader.TLabel')
        position_label.pack(side='right', padx=(10, 0))

        # Archetype pill badge
        try:
            from player_archetypes import get_archetype
            from modern_widgets import Pill
            arch = get_archetype(self.player)
            if arch and not str(arch).startswith("Depth") and "Backup" not in str(arch):
                Pill(name_frame, text=str(arch),
                     bg=self.app.ACCENT_COLOR).pack(side='right', padx=(10, 0))
        except Exception:
            pass
        
        # Enhanced player details in two rows
        details_frame = ttk.Frame(info_frame, style='PlayerTab.TFrame')
        details_frame.pack(fill='x')
        details_frame.grid_columnconfigure(0, weight=1)
        details_frame.grid_columnconfigure(1, weight=1)
        
        # First row of details
        row1_frame = ttk.Frame(details_frame, style='PlayerTab.TFrame')
        row1_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 3))
        
        ttk.Label(row1_frame, text=f"Age: {self.player.age}", style='PlayerInfo.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(row1_frame, text=f"Team: {self.player.team_name}", style='PlayerInfo.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(row1_frame, text=f"Nationality: {getattr(self.player, 'nationality', 'Unknown')}", style='PlayerInfo.TLabel').pack(side='left')
        
        # Second row of details
        row2_frame = ttk.Frame(details_frame, style='PlayerTab.TFrame')
        row2_frame.grid(row=1, column=0, columnspan=2, sticky='ew')
        
        ttk.Label(row2_frame, text=f"Height: {getattr(self.player, 'height', 'N/A')}", style='PlayerInfo.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(row2_frame, text=f"Weight: {getattr(self.player, 'weight', 'N/A')}", style='PlayerInfo.TLabel').pack(side='left', padx=(0, 20))
        ttk.Label(row2_frame, text=f"Shoots: {getattr(self.player, 'handedness', 'Unknown')}", style='PlayerInfo.TLabel').pack(side='left')
        
        # Overall rating with visual bar
        rating_frame = ttk.Frame(header_frame, style='PlayerTab.TFrame')
        rating_frame.grid(row=0, column=2, sticky='ns', padx=(15, 15))
        
        ttk.Label(rating_frame, text="Overall Rating", style='PlayerSubheader.TLabel').pack()
        overall = self.player.overall_rating()
        
        # Create visual rating bar
        rating_canvas = tk.Canvas(rating_frame, width=90, height=130, bg=self.app.BG_COLOR, highlightthickness=1, highlightbackground=self.app.TEXT_COLOR)
        rating_canvas.pack(pady=(5, 0))
        
        # Draw rating bar background
        rating_canvas.create_rectangle(25, 15, 65, 115, fill=self.app.CONTENT_BG, outline=self.app.TEXT_COLOR, width=2)
        
        # Draw rating bar fill (1-100 display scale)
        overall_100 = _to_100_scale(overall)
        bar_height = int(overall_100)  # bar is 100px tall
        bar_color = self._get_rating_color(overall)
        if bar_height > 0:
            rating_canvas.create_rectangle(27, 115-bar_height, 63, 113, fill=bar_color, outline="")
        
        # Draw scale markings and text
        rating_canvas.create_text(45, 10, text="100", fill=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 9))
        rating_canvas.create_text(45, 120, text="0", fill=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 9))
        rating_canvas.create_text(45, 125, text=str(overall_100), fill=self.app.HEADER_COLOR, font=(self.app.FONT_FAMILY, 14, 'bold'))
        
        # Contract status indicator
        contract_frame = ttk.Frame(header_frame, style='PlayerTab.TFrame')
        contract_frame.grid(row=0, column=3, sticky='ns', padx=(15, 0))
        
        ttk.Label(contract_frame, text="Contract", style='PlayerSubheader.TLabel').pack()
        
        if hasattr(self.player, 'contract') and self.player.contract:
            years_left = getattr(self.player.contract, 'years_left', 0)
            salary = getattr(self.player.contract, 'salary', 0)
            
            ttk.Label(contract_frame, text=f"{years_left} years", style='PlayerInfo.TLabel').pack(pady=(5, 2))
            ttk.Label(contract_frame, text=f"${salary:,}", style='PlayerInfo.TLabel').pack()
            
            # Contract value indicator
            if salary > 8000000:
                status_color = "#FFD700"  # Gold for superstar
                status_text = "SUPERSTAR"
            elif salary > 5000000:
                status_color = "#C0C0C0"  # Silver for star
                status_text = "STAR"
            elif salary > 2000000:
                status_color = "#CD7F32"  # Bronze for regular
                status_text = "VETERAN"
            else:
                status_color = "#808080"  # Gray for entry level
                status_text = "ENTRY LEVEL"
                
            status_canvas = tk.Canvas(contract_frame, width=80, height=20, bg=status_color, highlightthickness=1)
            status_canvas.pack(pady=(5, 0))
            status_canvas.create_text(40, 10, text=status_text, fill='black', font=(self.app.FONT_FAMILY, 8, 'bold'))
        else:
            ttk.Label(contract_frame, text="No Contract", style='PlayerInfo.TLabel').pack(pady=(5, 0))
    
    def _get_rating_color(self, rating):
        """Returns a color based on the rating value (native 1-100 scale)."""
        if rating >= 85:
            return "#4CAF50"  # Green for excellent
        elif rating >= 75:
            return "#8BC34A"  # Light green for very good
        elif rating >= 65:
            return "#A3D65C"  # Yellow-green for good
        elif rating >= 55:
            return "#FFC107"  # Yellow for average
        elif rating >= 40:
            return "#FF9800"  # Orange for below average
        else:
            return "#F44336"  # Red for poor

    def _create_basic_info_header(self, parent, row=0):
        """Creates header with player name and key information."""
        info_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        info_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))  # Changed to grid with sticky nsew
        
        # Player name with captain indicator
        name_text = self.player.full_name
        if self.player.captaincy:
            name_text += f" ({self.player.captaincy})"
        ttk.Label(info_frame, text=name_text, style='PlayerHeader.TLabel').pack(anchor='w')
        
        # Position, team, and key stats in one line
        overall = self.player.overall_rating()
        role = self.player.get_role()
        info_line = f"{self.player.primary_position.value} • {self.player.team_name} • Age {self.player.age} • Overall {_to_100_scale(overall)} • {role.value.replace('_', ' ').title()}"
        ttk.Label(info_frame, text=info_line, style='PlayerSubheader.TLabel').pack(anchor='w', pady=(2, 0))

    def _create_basic_info_compact(self, parent, row=0):
        """Creates compact basic player information."""
        info_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        info_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))  # Changed to grid with sticky nsew
        
        ttk.Label(info_frame, text="Player Information", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Create a 2-column grid for basic info
        info_grid = ttk.Frame(info_frame, style='PlayerTab.TFrame')
        info_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        info_grid.grid_columnconfigure(0, weight=1)
        info_grid.grid_columnconfigure(1, weight=1)
        
        basic_info = [
            ("Birthplace:", "Canada"),  # Placeholder
            ("Shoots:", "Left"),        # Placeholder
            ("Height:", "6'2\""),       # Placeholder
            ("Weight:", "200 lbs"),     # Placeholder
            ("Potential:", self.player.potential_grade),
            ("NHL Games:", str(self.player.nhl_games_played)),
            ("Morale:", f"{self.player.morale}/100"),
            ("Waiver Status:", "Exempt" if self.player.nhl_games_played < 160 else "Required")
        ]
        
        for i, (label, value) in enumerate(basic_info):
            row = i // 2
            col_base = (i % 2) * 2
            
            info_grid.grid_columnconfigure(col_base, weight=0)
            info_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(info_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(0, 5), pady=1
            )
            ttk.Label(info_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(0, 10), pady=1
            )

    def _create_contract_overview_compact(self, parent, row=1):
        """Creates compact contract overview section."""
        contract_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        contract_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))  # Changed to grid with sticky nsew
        
        ttk.Label(contract_frame, text="Contract Summary", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        contract_grid = ttk.Frame(contract_frame, style='PlayerTab.TFrame')
        contract_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        contract_grid.grid_columnconfigure(0, weight=1)
        contract_grid.grid_columnconfigure(1, weight=1)
        
        contract_info = [
            ("Salary:", f"${self.player.contract.salary:,}"),
            ("Years Left:", f"{self.player.contract.years_remaining}"),
            ("Signing Bonus:", f"${self.player.contract.signing_bonus:,}"),
            ("Trade Clause:", "Yes" if self.player.contract.no_trade_clause else "No")
        ]
        
        for i, (label, value) in enumerate(contract_info):
            row = i // 2
            col_base = (i % 2) * 2
            
            contract_grid.grid_columnconfigure(col_base, weight=0)
            contract_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(contract_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(0, 5), pady=1
            )
            ttk.Label(contract_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(0, 10), pady=1
            )

    def _create_key_attributes_overview_compact(self, parent, row=0):
        """Creates a compact overview of key attributes."""
        attr_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        attr_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))  # Changed to grid with sticky nsew
        
        ttk.Label(attr_frame, text="Key Attributes", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Determine key attributes based on position
        if self.player.primary_position == PlayerPosition.GOALIE:
            key_attrs = [
                ("Goaltending", self.player.goaltending),
                ("Reflexes", self.player.reflexes),
                ("Positioning", self.player.positioning),
                ("Rebound Control", self.player.rebound_control),
                ("Puck Handling", self.player.puck_handling),
                ("Composure", self.player.composure)
            ]
        else:
            key_attrs = [
                ("Skating", self.player.skating),
                ("Shooting", self.player.shooting),
                ("Passing", self.player.passing),
                ("Hockey IQ", self.player.hockey_iq),
                ("Checking", self.player.checking),
                ("Determination", self.player.determination)
            ]
        
        attr_grid = ttk.Frame(attr_frame, style='PlayerTab.TFrame')
        attr_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        attr_grid.grid_columnconfigure(0, weight=1)
        attr_grid.grid_columnconfigure(1, weight=1)
        
        for i, (label, value) in enumerate(key_attrs):
            row = i // 2
            col_base = (i % 2) * 2
            
            attr_grid.grid_columnconfigure(col_base, weight=0)
            attr_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(attr_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(0, 5), pady=1
            )
            
            style, text = self._get_attribute_style_and_text(value)
            ttk.Label(attr_grid, text=text, style=style, anchor='center', width=12).grid(
                row=row, column=col_base+1, padx=(0, 10), pady=1
            )

    def _create_performance_overview_compact(self, parent, row=1):
        """Creates compact performance overview."""
        perf_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        perf_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))  # Changed to grid with sticky nsew
        
        ttk.Label(perf_frame, text="Season Performance", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        stats_grid = ttk.Frame(perf_frame, style='PlayerTab.TFrame')
        stats_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        stats_grid.grid_columnconfigure(0, weight=1)
        stats_grid.grid_columnconfigure(1, weight=1)
        
        # Display current season stats
        if self.player.primary_position == PlayerPosition.GOALIE:
            stats_info = [
                ("Games:", str(self.player.games_played)),
                ("Wins:", str(self.player.wins)),
                ("Save %:", f"{self.player.save_percentage:.3f}"),
                ("GAA:", f"{self.player.goals_against_avg:.2f}")
            ]
        else:
            stats_info = [
                ("Games:", str(self.player.games_played)),
                ("Goals:", str(self.player.goals)),
                ("Assists:", str(self.player.assists)),
                ("Points:", str(self.player.points))
            ]
        
        for i, (label, value) in enumerate(stats_info):
            row = i // 2
            col_base = (i % 2) * 2
            
            stats_grid.grid_columnconfigure(col_base, weight=0)
            stats_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(stats_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(0, 5), pady=1
            )
            ttk.Label(stats_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(0, 10), pady=1
            )

    def _create_contract_overview(self, parent):
        """Creates contract overview section."""
        contract_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=15)
        contract_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(contract_frame, text="Contract Information", style='PlayerSubheader.TLabel').pack(anchor='w')
        
        info_grid = ttk.Frame(contract_frame, style='PlayerTab.TFrame')
        info_grid.pack(fill='x', pady=(10, 0))
        info_grid.grid_columnconfigure(0, weight=1)
        info_grid.grid_columnconfigure(1, weight=1)
        info_grid.grid_columnconfigure(2, weight=1)
        info_grid.grid_columnconfigure(3, weight=1)
        
        contract_info = [
            ("Annual Salary:", f"${self.player.contract.salary:,}"),
            ("Years Remaining:", f"{self.player.contract.years_remaining} years"),
            ("Signing Bonus:", f"${self.player.contract.signing_bonus:,}"),
            ("Trade Clause:", "No Movement" if self.player.contract.no_trade_clause else "None")
        ]
        
        for i, (label, value) in enumerate(contract_info):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(info_grid, text=label, style='PlayerInfo.TLabel').grid(row=row, column=col, sticky='w', padx=5, pady=2)
            ttk.Label(info_grid, text=value, style='PlayerValue.TLabel').grid(row=row, column=col+1, sticky='w', padx=5, pady=2)

    def _create_key_attributes_overview(self, parent):
        """Creates a quick overview of key attributes."""
        attr_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=15)
        attr_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(attr_frame, text="Key Attributes", style='PlayerSubheader.TLabel').pack(anchor='w')
        
        # Determine key attributes based on position
        if self.player.primary_position == PlayerPosition.GOALIE:
            key_attrs = [
                ("Goaltending", self.player.goaltending),
                ("Reflexes", self.player.reflexes),
                ("Positioning", self.player.positioning),
                ("Rebound Control", self.player.rebound_control)
            ]
        else:
            key_attrs = [
                ("Skating", self.player.skating),
                ("Shooting", self.player.shooting),
                ("Passing", self.player.passing),
                ("Hockey IQ", self.player.hockey_iq),
                ("Checking", self.player.checking),
                ("Determination", self.player.determination)
            ]
        
        attr_grid = ttk.Frame(attr_frame, style='PlayerTab.TFrame')
        attr_grid.pack(fill='x', pady=(10, 0))
        
        for i, (label, value) in enumerate(key_attrs):
            row = i // 3
            col = (i % 3) * 2
            attr_grid.grid_columnconfigure(col, weight=0)
            attr_grid.grid_columnconfigure(col+1, weight=1)
            
            ttk.Label(attr_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(row=row, column=col, sticky='w', padx=5, pady=2)
            
            style, text = self._get_attribute_style_and_text(value)
            ttk.Label(attr_grid, text=text, style=style, anchor='center', width=12).grid(row=row, column=col+1, padx=5, pady=2)

    def _create_performance_overview(self, parent):
        """Creates recent performance overview."""
        perf_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=15)
        perf_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(perf_frame, text="Current Season Performance", style='PlayerSubheader.TLabel').pack(anchor='w')
        
        stats_grid = ttk.Frame(perf_frame, style='PlayerTab.TFrame')
        stats_grid.pack(fill='x', pady=(10, 0))
        
        # Display current season stats
        if self.player.primary_position == PlayerPosition.GOALIE:
            stats_info = [
                ("Games Played:", str(self.player.games_played)),
                ("Wins:", str(self.player.wins)),
                ("Losses:", str(self.player.losses)),
                ("Save %:", f"{self.player.save_percentage:.3f}"),
                ("GAA:", f"{self.player.goals_against_avg:.2f}")
            ]
        else:
            stats_info = [
                ("Games Played:", str(self.player.games_played)),
                ("Goals:", str(self.player.goals)),
                ("Assists:", str(self.player.assists)),
                ("Points:", str(self.player.points)),
                ("PIM:", str(self.player.penalties_in_minutes))
            ]
        
        for i, (label, value) in enumerate(stats_info):
            row = i // 3
            col = (i % 3) * 2
            stats_grid.grid_columnconfigure(col, weight=0)
            stats_grid.grid_columnconfigure(col+1, weight=1)
            
            ttk.Label(stats_grid, text=label, style='PlayerInfo.TLabel').grid(row=row, column=col, sticky='w', padx=5, pady=2)
            ttk.Label(stats_grid, text=value, style='PlayerValue.TLabel').grid(row=row, column=col+1, sticky='w', padx=5, pady=2)

    def _create_attributes_tab(self):
        """Creates comprehensive attributes tab similar to EHM."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text='Attributes')
        
        # Main container with scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Bind canvas width changes to update scrollable frame width
        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Traits banner at top (if player has traits)
        self._create_traits_banner(scrollable_frame)

        # Create attribute sections
        if self.player.primary_position == PlayerPosition.GOALIE:
            self._create_goalie_attributes(scrollable_frame)
        else:
            self._create_skater_attributes(scrollable_frame)

    def _bar_color_for_value(self, disp):
        """Color for attribute bars: muted blue-gray scale, green only for elite."""
        if disp >= 85:
            return "#4CAF50"  # Elite - green
        elif disp >= 70:
            return "#7eb8ff"  # Good - light blue
        elif disp >= 55:
            return "#5a6c7d"  # Average - gray-blue
        elif disp >= 40:
            return "#8a6d3b"  # Below avg - muted amber
        else:
            return "#a04040"  # Poor - muted red

    def _draw_attr_bar(self, canvas, value):
        """Draw a clean progress bar for an attribute value (1-100)."""
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1:
            w = 200
        if h <= 1:
            h = 18
        # Track
        canvas.create_rectangle(0, 5, w, h - 5, fill="#23262e", outline="")
        # Fill
        color = self._bar_color_for_value(value)
        bar_w = max(3, int(w * value / 100))
        canvas.create_rectangle(0, 5, bar_w, h - 5, fill=color, outline="")

    def _create_traits_banner(self, parent, kind="talent"):
        """Display player traits as pills.

        kind='talent': on-ice traits (offense/defense/physical/skating/
        goalie) -- shown on the Attributes tab.
        kind='personality': mental traits (e.g. Clutch) -- shown on the
        Personality tab alongside personal details and allies.
        """
        try:
            from player_traits import get_player_traits
            traits = get_player_traits(self.player)
        except Exception:
            traits = []
        if kind == "talent":
            traits = [t for t in traits if getattr(t, "category", "") != "mental"]
            title = "Talent Traits"
        else:
            traits = [t for t in traits if getattr(t, "category", "") == "mental"]
            title = "Personality Traits"
        if not traits:
            return

        banner = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        banner.pack(fill='x', padx=8, pady=(8, 4))

        ttk.Label(banner, text=title, style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 6))

        pills_frame = ttk.Frame(banner, style='PlayerTab.TFrame')
        pills_frame.pack(fill='x')

        for trait in traits:
            pill = tk.Label(
                pills_frame, text=f" {trait.name} ",
                bg="#1e3a5f", fg="#8ec2ff",
                font=(self.app.FONT_FAMILY, 11, "bold"),
                padx=10, pady=3, cursor="hand2",
            )
            pill.pack(side="left", padx=(0, 8), pady=2)
            # Hover tooltip with trait description
            self._bind_trait_tooltip(pill, trait.name, trait.description)

    def _bind_trait_tooltip(self, widget, title, description):
        """Simple hover tooltip for trait pills."""
        tooltip = None

        def show(event):
            nonlocal tooltip
            if tooltip:
                return
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
            frame = tk.Frame(tooltip, bg="#1a1d24", padx=10, pady=8)
            frame.pack()
            tk.Label(frame, text=title, bg="#1a1d24", fg="#8ec2ff",
                     font=(self.app.FONT_FAMILY, 11, "bold")).pack(anchor="w")
            tk.Label(frame, text=description, bg="#1a1d24", fg="#c0c5ce",
                     font=(self.app.FONT_FAMILY, 10), wraplength=280,
                     justify="left").pack(anchor="w", pady=(4, 0))

        def hide(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _new_scrollable_tab(self, title):
        """Creates a scrollable notebook tab; returns the scrollable frame."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text=title)

        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)

        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return scrollable_frame

    def _get_league(self):
        """Best-effort league accessor for the card's social-circle lookups."""
        lg = getattr(self.app, 'league', None)
        if lg is None:
            gm = getattr(self.app, 'game_manager', None)
            lg = getattr(gm, 'league', None) if gm is not None else None
        return lg

    def _get_player_team(self, league):
        if league is None:
            return None
        tname = getattr(self.player, 'team_name', '')
        for t in getattr(league, 'teams', []) or []:
            if getattr(t, 'team_name', '') == tname:
                return t
        return None

    def _create_personality_tab(self):
        """Personality, personal details, and the player's social circle."""
        is_goalie = self.player.primary_position == PlayerPosition.GOALIE
        scrollable_frame = self._new_scrollable_tab('Personality')

        # Personality traits (mental-category pills, e.g. Clutch)
        self._create_traits_banner(scrollable_frame, kind="personality")

        # Personal details live here now, beside personality
        self._create_personal_details_section(scrollable_frame)

        # Reputation / standing (moved off the Attributes tab)
        self._create_personality_sections(scrollable_frame, is_goalie=is_goalie)

        # Social circle: family, friends, favourite teammate/staff, rivals
        self._create_close_allies_section(scrollable_frame)

    def _personal_details_items(self):
        """Personal-detail rows shared by the Personality tab."""
        return [
            ("Full Name:", self.player.full_name),
            ("Date of Birth:", f"{getattr(self.player, 'birth_date', 'Unknown')}"),
            ("Birthplace:", f"{getattr(self.player, 'birthplace', 'Canada')}"),
            ("Nationality:", f"{getattr(self.player, 'nationality', 'Canadian')}"),
            ("Height:", f"{getattr(self.player, 'height', '6ft 0in')}"),
            ("Weight:", f"{getattr(self.player, 'weight', '180')} lbs"),
            ("Shoots/Catches:", f"{getattr(self.player, 'handedness', 'Right')}"),
            ("Draft Year:", f"{getattr(self.player, 'draft_year', 'Undrafted')}"),
            ("Draft Position:", f"{getattr(self.player, 'draft_position', 'N/A')}"),
            ("Years Pro:", f"{max(0, self.player.age - 18)} years"),
        ]

    def _create_personal_details_section(self, parent):
        section = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        section.pack(fill='x', padx=8, pady=4)

        ttk.Label(section, text="Personal Details", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))

        grid = ttk.Frame(section, style='PlayerTab.TFrame')
        grid.pack(fill='x')
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1 if c % 2 else 0)

        items = self._personal_details_items()
        try:
            import reputation_system as rs
            items.append(("Social Group:", rs.player_social_group(self.player)))
        except Exception:
            pass

        for i, (label, value) in enumerate(items):
            r, c = divmod(i, 2)
            ttk.Label(grid, text=label, style='PlayerInfo.TLabel').grid(
                row=r, column=c * 2, sticky='w', padx=(0, 10), pady=3)
            ttk.Label(grid, text=str(value), style='PlayerValue.TLabel').grid(
                row=r, column=c * 2 + 1, sticky='w', padx=(0, 18), pady=3)

    @staticmethod
    def _bond_label(score):
        if score >= 70:
            return "Close friend"
        if score >= 50:
            return "Good friend"
        return "Friend"

    @staticmethod
    def _rival_label(score):
        if score <= -70:
            return "Bitter rival"
        if score <= -50:
            return "Rival"
        return "Frosty"

    @staticmethod
    def _fit_label(fit):
        if fit >= 0.5:
            return "Tight bond"
        if fit >= 0.2:
            return "Good rapport"
        if fit >= -0.2:
            return "Professional"
        return "Friction"

    def _favourite_staff(self, team):
        """Coach on the player's team with the best player-coach fit."""
        if team is None:
            return None
        try:
            import reputation_system as rs
            from game_classes import StaffRole
            coaching_roles = {
                StaffRole.HEAD_COACH, StaffRole.ASSISTANT_COACH,
                StaffRole.ASSOCIATE_COACH, StaffRole.GOALIE_COACH,
                StaffRole.POWER_PLAY_COACH, StaffRole.PENALTY_KILL_COACH,
                StaffRole.SKILLS_COACH,
            }
            best, best_fit = None, -2.0
            for s in getattr(team, 'staff', []) or []:
                if getattr(s, 'role', None) not in coaching_roles:
                    continue
                try:
                    fit = rs.coach_player_fit(s, self.player)
                except Exception:
                    continue
                if fit > best_fit:
                    best, best_fit = s, fit
            if best is None:
                return None
            return {"staff": best, "fit": best_fit}
        except Exception:
            return None

    def _allies_data(self):
        """Gather family, friends, favourite teammate/staff, and rivals."""
        data = {"family": [], "friends": [], "teammate": None,
                "staff": None, "rivals": []}
        try:
            import reputation_system as rs
        except Exception:
            return data

        league = self._get_league()
        team = self._get_player_team(league)
        roster = list(getattr(team, 'roster', []) or []) if team else []
        all_players = []
        if league is not None:
            for t in getattr(league, 'teams', []) or []:
                all_players.extend(getattr(t, 'roster', []) or [])
            # Family links can point at free agents or draft prospects
            # (generation links across rosters + free agents + prospects);
            # resolve them too.
            all_players.extend(getattr(league, 'free_agents', []) or [])
            all_players.extend(getattr(league, 'draft_prospects', []) or [])
        by_id = {p.id: p for p in all_players}

        family_ids = set(getattr(self.player, 'family_ids', []) or [])
        for fid in family_ids:
            fp = by_id.get(fid)
            if fp is not None:
                data["family"].append(fp)

        try:
            friends = rs.get_friends(self.player, all_players, n=5)
            data["friends"] = [f for f in friends
                               if f["player"].id not in family_ids][:3]
        except Exception:
            pass

        try:
            tm = rs.get_friends(self.player, roster, n=1)
            data["teammate"] = tm[0] if tm else None
        except Exception:
            pass

        data["staff"] = self._favourite_staff(team)

        try:
            data["rivals"] = rs.get_rivals(self.player, roster, league, n=3)
        except Exception:
            pass
        return data

    def _create_close_allies_section(self, parent):
        """Family, best friends, favourite teammate/staff, and rivals."""
        data = self._allies_data()

        section = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        section.pack(fill='x', padx=8, pady=4)

        ttk.Label(section, text="Close Allies", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 4))

        def _subsection(title):
            ttk.Label(section, text=title, style='PlayerInfo.TLabel',
                      font=(self.app.FONT_FAMILY, 12, 'bold')).pack(anchor='w', pady=(8, 2))

        def _row(name, detail, descriptor):
            row = ttk.Frame(section, style='PlayerTab.TFrame')
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=name, style='PlayerValue.TLabel', width=26).pack(side='left')
            ttk.Label(row, text=detail, style='PlayerInfo.TLabel').pack(side='left', padx=(8, 0))
            if descriptor:
                ttk.Label(row, text=f"\u2022 {descriptor}",
                          style='PlayerInfo.TLabel').pack(side='left', padx=(8, 0))

        def _empty(text):
            ttk.Label(section, text=text, style='PlayerInfo.TLabel').pack(anchor='w', pady=2)

        # Family
        _subsection("Family")
        if data["family"]:
            for fp in data["family"]:
                pos = getattr(getattr(fp, 'primary_position', ''), 'value', '')
                _row(fp.full_name,
                     f"{getattr(fp, 'team_name', '')} {('\u2022 ' + pos) if pos else ''}".strip(),
                     "Family")
        else:
            _empty("No family in the league.")

        # Best friends in the league
        _subsection("Best Friends in the League")
        if data["friends"]:
            for f in data["friends"]:
                p, s = f["player"], f["score"]
                _row(p.full_name, getattr(p, 'team_name', ''),
                     self._bond_label(s))
        else:
            _empty("No close friendships yet \u2014 bonds form as the season unfolds.")

        # Favourite teammate
        _subsection("Favourite Teammate")
        if data["teammate"]:
            p, s = data["teammate"]["player"], data["teammate"]["score"]
            pos = getattr(getattr(p, 'primary_position', ''), 'value', '')
            _row(p.full_name, pos, self._bond_label(s))
        else:
            _empty("No standout bond on the roster yet.")

        # Favourite staff
        _subsection("Favourite Staff")
        if data["staff"]:
            s, fit = data["staff"]["staff"], data["staff"]["fit"]
            role = getattr(getattr(s, 'role', ''), 'value', '')
            _row(s.full_name, role, self._fit_label(fit))
        else:
            _empty("No coaching staff found.")

        # Rivals
        _subsection("Rivals")
        if data["rivals"]:
            for r in data["rivals"]:
                _row(r.get("name", "?"), r.get("origin", ""),
                     self._rival_label(r.get("score", 0)))
        else:
            _empty("No bad blood on record.")

    def _create_attribute_section(self, parent, title, attributes, row_start=0):
        """Creates a clean section of attributes with progress bars.

        Modern design: attribute name + subtle bar + numeric value,
        replacing the old colored-badge grid.
        """
        section_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        section_frame.pack(fill='x', padx=8, pady=4)

        # Section title
        ttk.Label(section_frame, text=title, style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))

        # Two-column layout for compactness
        cols_frame = ttk.Frame(section_frame, style='PlayerTab.TFrame')
        cols_frame.pack(fill='x')
        cols_frame.grid_columnconfigure(0, weight=1)
        cols_frame.grid_columnconfigure(1, weight=1)

        left_col = ttk.Frame(cols_frame, style='PlayerTab.TFrame')
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        right_col = ttk.Frame(cols_frame, style='PlayerTab.TFrame')
        right_col.grid(row=0, column=1, sticky='nsew', padx=(12, 0))

        for i, (attr_name, attr_key) in enumerate(attributes):
            col = left_col if i % 2 == 0 else right_col

            row = ttk.Frame(col, style='PlayerTab.TFrame')
            row.pack(fill='x', pady=3)

            # Attribute name
            ttk.Label(row, text=attr_name, style='PlayerInfo.TLabel', width=18).pack(side='left')

            # Value on the native 1-100 display scale
            raw = getattr(self.player, attr_key, 10)
            disp = _to_100_scale(raw)

            # Bar
            bar = tk.Canvas(row, height=16, bg=self.app.CONTENT_BG, highlightthickness=0)
            # Numeric value (pack right first so bar doesn't squeeze it out)
            ttk.Label(row, text=str(disp), style='PlayerValue.TLabel', width=4).pack(side='right', padx=(6, 0))
            bar.pack(side='left', fill='x', expand=True, padx=(6, 0))
            bar.bind('<Configure>', lambda e, c=bar, v=disp: self._draw_attr_bar(c, v))
            # Draw immediately too (in case Configure already fired)
            bar.after(10, lambda c=bar, v=disp: self._draw_attr_bar(c, v))

    def _create_text_attribute_section(self, parent, title, items):
        """A section of label/value rows for non-numeric attributes
        (development arc, squad status, form readouts). Same two-column
        rhythm as the bar sections."""
        section_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        section_frame.pack(fill='x', padx=8, pady=4)

        ttk.Label(section_frame, text=title, style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))

        cols_frame = ttk.Frame(section_frame, style='PlayerTab.TFrame')
        cols_frame.pack(fill='x')
        cols_frame.grid_columnconfigure(0, weight=1)
        cols_frame.grid_columnconfigure(1, weight=1)

        left_col = ttk.Frame(cols_frame, style='PlayerTab.TFrame')
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        right_col = ttk.Frame(cols_frame, style='PlayerTab.TFrame')
        right_col.grid(row=0, column=1, sticky='nsew', padx=(12, 0))

        for i, (label, value) in enumerate(items):
            col = left_col if i % 2 == 0 else right_col
            row = ttk.Frame(col, style='PlayerTab.TFrame')
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=label, style='PlayerInfo.TLabel', width=18).pack(side='left')
            ttk.Label(row, text=str(value), style='PlayerValue.TLabel').pack(side='left', padx=(6, 0))

    def _ecosystem_development_rows(self):
        """Text rows for the Development section (ecosystem-exclusive)."""
        arc = getattr(self.player, "development_arc", "standard") or "standard"
        arc_disp = arc.replace("_", " ").title()
        grade = getattr(self.player, "potential_grade", "?") or "?"
        return [("Development Arc", arc_disp), ("Potential Grade", grade)]

    def _ecosystem_reputation_rows(self, is_goalie=False):
        """Text rows for the Reputation & Personality section."""
        rows = [("Squad Status", getattr(self.player, "squad_status", "Rotation") or "Rotation")]
        # Ambition: what drives his contract decisions (cup/money/ice/...).
        try:
            import player_decision as _pd
            _pd.ensure_decision_fields(self.player)
            _amb = getattr(self.player, "ambition", "") or ""
            _labels = {"cup": "Stanley Cup", "money": "Money",
                       "ice_time": "Ice Time", "stability": "Stability",
                       "home": "Hometown"}
            if _amb in _labels:
                rows.append(("Ambition", _labels[_amb]))
        except Exception:
            pass
        if is_goalie:
            temp = getattr(self.player, "goalie_temperament", "") or ""
            if temp:
                rows.append(("Temperament", temp.title()))
        return rows

    def _ecosystem_form_rows(self):
        """Text rows for the Form & Chemistry section (ecosystem-exclusive)."""
        try:
            mf = float(getattr(self.player, "mesh_form", 0.0) or 0.0)
        except (TypeError, ValueError):
            mf = 0.0
        if mf >= 0.33:
            form_disp = f"Hot (+{mf:.2f})"
        elif mf >= 0.10:
            form_disp = f"Warming (+{mf:.2f})"
        elif mf <= -0.33:
            form_disp = f"Cold ({mf:.2f})"
        elif mf <= -0.10:
            form_disp = f"Cooling ({mf:.2f})"
        else:
            form_disp = f"Neutral ({mf:+.2f})"
        streak = getattr(self.player, "mesh_streak", 0) or 0
        line_chem = getattr(self.player, "line_chemistry", 10) or 10
        team_chem = getattr(self.player, "team_chemistry", 10) or 10
        return [
            ("Mesh Form", form_disp),
            ("Mesh Streak", f"{streak} games"),
            ("Line Chemistry", f"{line_chem}/20"),
            ("Team Chemistry", f"{team_chem}/20"),
        ]

    def _create_ecosystem_attribute_sections(self, parent, is_goalie=False):
        """Puck Dynasty-exclusive attribute sections, appended after the
        EHM-style groups on the Attributes tab.

        Personality-flavored sections (reputation, standing) live on the
        Personality tab instead -- see _create_personality_sections.
        """
        # Development: coachability drives the assistant-coach dev bumps,
        # the arc shapes each career's trajectory, the grade is the scout's read.
        self._create_attribute_section(parent, "Development", [
            ("Coachability", "coachability"),
            ("Work Ethic", "work_ethic"),
            ("Adaptability", "adaptability"),
        ])
        self._create_text_attribute_section(
            parent, "Development Path", self._ecosystem_development_rows())

        # Form & Chemistry: the perfect-mesh form tracker and chemistry reads.
        self._create_text_attribute_section(
            parent, "Form & Chemistry", self._ecosystem_form_rows())

    def _create_personality_sections(self, parent, is_goalie=False):
        """Reputation/personality sections shared by the Personality tab."""
        # Loyalty + ambition (player_decision.py) seed lazily so old saves
        # show real values, not blanks.
        try:
            import player_decision as _pd
            _pd.ensure_decision_fields(self.player)
        except Exception:
            pass
        # Reputation & Personality: the reputation ratchet, visible
        # controversy (hotheads cost less in trades), happiness at the club.
        self._create_attribute_section(parent, "Reputation & Personality", [
            ("Reputation", "reputation"),
            ("Controversy", "controversy"),
            ("Happiness", "happiness"),
            ("Loyalty", "loyalty"),
        ])
        self._create_text_attribute_section(
            parent, "Standing", self._ecosystem_reputation_rows(is_goalie))

    def _create_skater_attributes(self, parent):
        """Creates attribute sections for skaters (non-goalies)."""
        
        # Technical/Offensive Attributes
        technical_attrs = [
            ("Shooting", "shooting"),
            ("Wrist Shot", "wristshot"),
            ("Slap Shot", "slapshot"),
            ("Shooting Accuracy", "shooting_accuracy"),
            ("Shooting Power", "shooting_power"),
            ("One Timer", "one_timer"),
            ("Backhand", "backhand"),
            ("Deflections", "deflections")
        ]
        self._create_attribute_section(parent, "Shooting & Scoring", technical_attrs)
        
        # Passing & Playmaking
        passing_attrs = [
            ("Passing", "passing"),
            ("Passing Accuracy", "passing_accuracy"),
            ("Passing Creativity", "passing_creativity"),
            ("Vision", "vision"),
            ("Creativity", "creativity"),
            ("Hockey IQ", "hockey_iq"),
            ("Decision Making", "decision_making"),
            ("Anticipation", "anticipation")
        ]
        self._create_attribute_section(parent, "Passing & Playmaking", passing_attrs)
        
        # Skating & Movement
        skating_attrs = [
            ("Skating", "skating"),
            ("Speed", "speed"),
            ("Acceleration", "acceleration"),
            ("Agility", "agility"),
            ("Balance", "balance"),
            ("Endurance", "endurance"),
            ("Stamina", "stamina"),
        ]
        self._create_attribute_section(parent, "Skating", skating_attrs)

        # Puck Skills (previously defined but never displayed)
        puck_skills = [
            ("Stickhandling", "stickhandling"),
            ("Deking", "deking"),
            ("Puck Protection", "puck_protection"),
            ("Off the Puck", "off_the_puck"),
            ("Loose Puck", "loose_puck"),
        ]
        self._create_attribute_section(parent, "Puck Skills", puck_skills)

        # Transition & Forecheck
        transition_attrs = [
            ("First Pass", "first_pass"),
            ("Breakout Passes", "breakout_passes"),
            ("Forechecking", "forechecking"),
        ]
        self._create_attribute_section(parent, "Transition & Forecheck", transition_attrs)
        
        # Defensive Attributes
        defensive_attrs = [
            ("Checking", "checking"),
            ("Body Check", "bodycheck"),
            ("Poke Check", "pokecheck"),
            ("Shot Blocking", "shot_blocking"),
            ("Defensive Awareness", "defensive_awareness"),
            ("Aggressiveness", "aggressiveness"),
            ("Discipline", "discipline"),
            ("Screen Shots", "screen_shots")
        ]
        self._create_attribute_section(parent, "Defensive Skills", defensive_attrs)
        
        # Physical & Mental combined
        physical_mental_attrs = [
            ("Strength", "strength"),
            ("Durability", "durability"),
            ("Injury Proneness", "injury_proneness"),
            ("Work Rate", "work_rate"),
            ("Determination", "determination"),
            ("Teamwork", "teamwork"),
            ("Leadership", "leadership"),
            ("Composure", "composure")
        ]
        self._create_attribute_section(parent, "Physical & Mental", physical_mental_attrs)
        
        # Tendencies: 0-100, higher shoots/hits more
        tendency_attrs = [
            ("Shoot Tendency", "shoot_pass_tendency"),
            ("Hitting Tendency", "hitting_tendency"),
        ]
        self._create_attribute_section(parent, "Tendencies", tendency_attrs)

        # Character & Consistency
        character_attrs = [
            ("Confidence", "confidence"),
            ("Flair", "flair"),
            ("Morale", "morale"),
            ("Consistency", "consistency"),
            ("Important Matches", "important_matches"),
            ("Focus", "focus"),
            ("Pressure Player", "pressure_player"),
            ("Offensive Awareness", "offensive_awareness")
        ]
        self._create_attribute_section(parent, "Character & Mentality", character_attrs)
        
        # Faceoffs: every skater takes draws; centers get the full read
        faceoff_attrs = [("Faceoffs", "faceoffs")]
        if self.player.primary_position == PlayerPosition.CENTER:
            faceoff_attrs.append(("Faceoff Wins", "faceoff_wins"))
        self._create_attribute_section(parent, "Faceoffs", faceoff_attrs)

        # Puck Dynasty ecosystem exclusives
        self._create_ecosystem_attribute_sections(parent, is_goalie=False)

    def _create_goalie_attributes(self, parent):
        """Creates attribute sections for goalies."""
        
        # Core Goaltending
        core_attrs = [
            ("Goaltending", "goaltending"),
            ("Reflexes", "reflexes"),
            ("Positioning", "positioning"),
            ("Rebound Control", "rebound_control"),
            ("Glove Hand", "glove_hand"),
            ("Stick Side", "stick_side"),
            ("Breakaway Skill", "breakaway_skill"),
            ("Puck Handling", "puck_handling")
        ]
        self._create_attribute_section(parent, "Core Goaltending", core_attrs)
        
        # Movement & Mental
        movement_attrs = [
            ("Skating", "skating"),
            ("Speed", "speed"),
            ("Agility", "agility"),
            ("Balance", "balance"),
            ("Anticipation", "anticipation"),
            ("Decision Making", "decision_making"),
            ("Focus", "focus"),
            ("Vision", "vision")
        ]
        self._create_attribute_section(parent, "Movement & Mental", movement_attrs)
        
        # Physical & Character
        physical_attrs = [
            ("Strength", "strength"),
            ("Endurance", "endurance"),
            ("Durability", "durability"),
            ("Injury Proneness", "injury_proneness"),
            ("Determination", "determination"),
            ("Composure", "composure"),
            ("Consistency", "consistency"),
            ("Important Matches", "important_matches")
        ]
        self._create_attribute_section(parent, "Physical & Character", physical_attrs)
        
        # Additional Mental Attributes
        mental_attrs = [
            ("Confidence", "confidence"),
            ("Morale", "morale"),
            ("Teamwork", "teamwork"),
            ("Leadership", "leadership")
        ]
        self._create_attribute_section(parent, "Mental & Leadership", mental_attrs)

        # Puck Dynasty ecosystem exclusives (incl. goalie temperament)
        self._create_ecosystem_attribute_sections(parent, is_goalie=True)

    def _create_stats_tab(self):
        """Creates detailed statistics tab with career history and projections."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text='Statistics')
        
        # Main container with scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Bind canvas width changes to update scrollable frame width
        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Current season summary
        self._create_current_season_stats(scrollable_frame)
        
        # Career statistics table
        self._create_career_stats_table(scrollable_frame)
        
        # Advanced statistics
        self._create_advanced_stats(scrollable_frame)
        
        # Performance trends
        self._create_performance_trends(scrollable_frame)

    def _create_current_season_stats(self, parent):
        """Creates current season statistics summary."""
        stats_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        stats_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(stats_frame, text="2024-25 Season Statistics", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Stats grid - 4 columns for better space usage
        stats_grid = ttk.Frame(stats_frame, style='PlayerTab.TFrame')
        stats_grid.pack(fill='x')
        
        if self.player.primary_position == PlayerPosition.GOALIE:
            current_stats = [
                ("Games Played", "0"),
                ("Wins", "0"),
                ("Losses", "0"),
                ("OT Losses", "0"),
                ("Minutes", "0:00"),
                ("Goals Against", "0"),
                ("GAA", "0.00"),
                ("Saves", "0"),
                ("Save %", "0.000"),
                ("Shutouts", "0"),
                ("Shots Faced", "0"),
                ("Quality Starts", "0")
            ]
        else:
            current_stats = [
                ("Games Played", "0"),
                ("Goals", str(self.player.stats.goals)),
                ("Assists", str(self.player.stats.assists)),
                ("Points", str(self.player.stats.points)),
                ("Plus/Minus", "+0"),
                ("PIM", str(self.player.stats.penalties_in_minutes)),
                ("PP Goals", "0"),
                ("PP Assists", "0"),
                ("SH Goals", "0"),
                ("GW Goals", "0"),
                ("Shots", "0"),
                ("Shooting %", "0.0%")
            ]
        
        # Display in 4-column layout
        for i, (label, value) in enumerate(current_stats):
            row = i // 4
            col_base = (i % 4) * 2
            
            stats_grid.grid_columnconfigure(col_base, weight=0)
            stats_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(stats_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(2, 1), pady=1
            )
            ttk.Label(stats_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
            )

    def _create_career_stats_table(self, parent):
        """Creates career statistics table."""
        table_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        table_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(table_frame, text="Career Statistics", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Create treeview for career stats
        if self.player.primary_position == PlayerPosition.GOALIE:
            columns = {
                'season': ('Season', 70),
                'team': ('Team', 80),
                'league': ('Lg', 40),
                'gp': ('GP', 35),
                'w': ('W', 30),
                'l': ('L', 30),
                'otl': ('OTL', 35),
                'min': ('MIN', 50),
                'ga': ('GA', 35),
                'gaa': ('GAA', 45),
                'sv': ('SV', 35),
                'svp': ('SV%', 45),
                'so': ('SO', 30)
            }
        else:
            columns = {
                'season': ('Season', 70),
                'team': ('Team', 80),
                'league': ('Lg', 40),
                'gp': ('GP', 35),
                'g': ('G', 30),
                'a': ('A', 30),
                'p': ('P', 35),
                'pm': ('+/-', 35),
                'pim': ('PIM', 35),
                'ppg': ('PPG', 35),
                'shg': ('SHG', 35),
                'gwg': ('GWG', 35)
            }
        
        # Create the treeview
        career_tree = self.app._create_treeview(table_frame, columns)  # Remove fixed height
        career_tree.pack(fill='x', pady=(0, 5))
        
        # Add sample career data (in a real game, this would come from saved statistics)
        sample_seasons = [
            f"202{i}-{i+1}" for i in range(3, min(4 + max(1, self.player.age - 18), 7))
        ]
        
        for season in sample_seasons:
            if self.player.primary_position == PlayerPosition.GOALIE:
                career_tree.insert('', 'end', values=(
                    season, self.player.team_name, "NHL", "0", "0", "0", "0", "0:00", "0", "0.00", "0", "0.000", "0"
                ))
            else:
                # Use current season stats as placeholder for previous seasons
                career_tree.insert('', 'end', values=(
                    season, self.player.team_name, "NHL", "0", 
                    self.player.stats.goals, self.player.stats.assists, self.player.stats.points,
                    "+0", self.player.stats.penalties_in_minutes, "0", "0", "0"
                ))

    def _create_advanced_stats(self, parent):
        """Per-player advanced analytics on the Statistics tab.

        Mirrors the legacy card's deep dive: the same department-lens
        metrics, the same honest ±CI labeling, the same as-of line.
        The numbers YOUR club sees come through YOUR analytics
        department -- modeled metrics carry the department's noise and
        confidence intervals, observed box-score facts are exact.
        """
        import advanced_metrics as am
        p = self.player
        try:
            is_goalie = "GOALIE" in str(p.primary_position).upper()
        except Exception:
            is_goalie = False

        lens = None
        try:
            team = getattr(self.app, "user_team", None)
            date_str = str(getattr(self.app, "current_date", "") or "")
            if team is not None:
                if is_goalie:
                    lens = am.display_goalie_metrics(p, team, date_str)
                else:
                    lens = am.display_skater_metrics(p, team, date_str)
        except Exception:
            lens = None

        def _val(field, fallback):
            if lens is not None and field in lens.values:
                return lens.values[field]
            return fallback

        def _with_ci(field, text, pct100=False):
            if lens is not None and field in lens.ci:
                ci = lens.ci[field]
                if text.rstrip().endswith("%"):
                    if pct100:
                        return f"{text} ±{ci:.1f} pts"
                    return f"{text} ±{ci * 100:.1f} pts"
                return f"{text} ±{ci:.1f}"
            return text

        def _glossary_tip(event, text):
            try:
                tip = tk.Toplevel()
                tip.wm_overrideredirect(True)
                tip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
                tk.Label(tip, text=text, wraplength=280, justify="left",
                         background="#ffffe0", relief="solid",
                         borderwidth=1).pack()
                event.widget.bind("<Leave>", lambda _e: tip.destroy(),
                                  add="+")
                tip.after(4000, tip.destroy)
            except Exception:
                pass

        advanced_frame = ttk.Frame(parent, style='PlayerPanel.TFrame',
                                   padding=10)
        advanced_frame.pack(fill='x', padx=5, pady=3)

        ttk.Label(advanced_frame, text="Advanced Analytics",
                  style='PlayerSubheader.TLabel').pack(anchor='w',
                                                       pady=(0, 2))
        if lens is not None:
            lag = lens.lag_days
            ttk.Label(
                advanced_frame,
                text=(f"{lens.tier}  •  models as of {lens.as_of} "
                      f"(rebuilt every {lag} day{'s' if lag != 1 else ''})"),
                style='PlayerInfo.TLabel').pack(anchor='w', pady=(0, 2))
        ttk.Label(
            advanced_frame,
            text=("Estimates, not tracking data: modeled metrics show your "
                  "department's confidence interval (±); observed box-score "
                  "facts are exact. Hover ⓘ on any metric for what it is "
                  "(and isn't)."),
            style='PlayerInfo.TLabel',
            wraplength=900).pack(anchor='w', pady=(0, 8))

        def _section(title, rows):
            ttk.Label(advanced_frame, text=title,
                      style='PlayerSubheader.TLabel').pack(anchor='w',
                                                           pady=(8, 4))
            for label, value, tip in rows:
                row = ttk.Frame(advanced_frame, style='PlayerTab.TFrame')
                row.pack(fill='x', pady=1)
                ttk.Label(row, text=label, style='PlayerInfo.TLabel',
                          width=28).pack(side='left')
                ttk.Label(row, text=value,
                          style='PlayerValue.TLabel').pack(side='left')
                if tip:
                    dot = ttk.Label(row, text="ⓘ",
                                    style='PlayerInfo.TLabel',
                                    cursor="hand2")
                    dot.pack(side='left', padx=6)
                    dot.bind("<Enter>",
                             lambda e, t=tip: _glossary_tip(e, t))

        try:
            if is_goalie:
                m = am.goalie_advanced(p)
                _section("Goaltending — Above Expected", [
                    ("GSAx",
                     _with_ci("gsax", f"{_val('gsax', m.gsax):+.1f}"),
                     am.GLOSSARY.get("GSAx")),
                    ("GSAA", f"{_val('gsaa', m.gsaa):+.1f}",
                     am.GLOSSARY.get("GSAA")),
                    ("High-danger SV%",
                     _with_ci("hdsv_pct",
                              f"{_val('hdsv_pct', m.hdsv_pct):.3f}"),
                     am.GLOSSARY.get("HDSV%")),
                    ("Quality-start %",
                     _with_ci("qs_pct",
                              f"{_val('qs_pct', m.qs_pct):.1%}"),
                     am.GLOSSARY.get("QS%")),
                ])
                _section("Workload", [
                    ("Save %", f"{_val('sv_pct', m.sv_pct):.3f}", None),
                    ("GAA", f"{_val('gaa', m.gaa):.2f}", None),
                    ("Shots against / 60",
                     f"{_val('sa_per60', m.sa_per60):.1f}", None),
                ])
            else:
                m = am.skater_advanced(p)
                _section("Offense — Finishing & Creation", [
                    ("Shooting %",
                     f"{_val('sh_pct', m.sh_pct):.1f}%",
                     am.GLOSSARY.get("SH%")),
                    ("Individual xG",
                     _with_ci("ixg", f"{_val('ixg', m.ixg):.1f}"),
                     am.GLOSSARY.get("ixG")),
                    ("Goals / 60",
                     f"{_val('g_per60', m.g_per60):.2f}", None),
                    ("Points / 60",
                     f"{_val('p_per60', m.p_per60):.2f}",
                     am.GLOSSARY.get("P/60")),
                    ("Game Score",
                     f"{_val('game_score', m.game_score):.1f}",
                     am.GLOSSARY.get("Game Score")),
                ])
                _section("Possession — Driving Play", [
                    ("Corsi %",
                     _with_ci("cf_pct",
                              f"{_val('cf_pct', m.cf_pct):.1f}%", True),
                     am.GLOSSARY.get("CF%")),
                    ("Fenwick %",
                     _with_ci("ff_pct",
                              f"{_val('ff_pct', m.ff_pct):.1f}%", True),
                     am.GLOSSARY.get("FF%")),
                    ("Expected-goal share",
                     _with_ci("xgf_pct",
                              f"{_val('xgf_pct', m.xgf_pct):.1f}%", True),
                     am.GLOSSARY.get("xGF%")),
                    ("Offensive-zone starts",
                     _with_ci("oz_pct",
                              f"{_val('oz_pct', m.oz_pct):.1f}%", True),
                     am.GLOSSARY.get("OZ%")),
                ])
                _section("Defense & Luck", [
                    ("PDO",
                     _with_ci("pdo", f"{_val('pdo', m.pdo):.3f}"),
                     am.GLOSSARY.get("PDO")),
                    ("Hits", str(int(_val("hits", m.hits))), None),
                    ("Blocked shots", str(int(_val("blocks", m.blocks))),
                     None),
                ])
        except Exception as e:
            ttk.Label(advanced_frame,
                      text=f"Analytics unavailable ({e})",
                      style='PlayerInfo.TLabel').pack(anchor='w')

    def _create_performance_trends(self, parent):
        """Creates performance trends and notes section."""
        trends_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        trends_frame.pack(fill='x', padx=5, pady=3)
        
        ttk.Label(trends_frame, text="Performance Trends & Notes", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Performance indicators - 4 columns
        perf_grid = ttk.Frame(trends_frame, style='PlayerTab.TFrame')
        perf_grid.pack(fill='x', pady=(0, 10))
        
        # Sample performance indicators
        performance_notes = [
            ("Form", "Good"),
            ("Consistency", f"{_to_100_scale(self.player.consistency)}"),
            ("Big Game Player", f"{_to_100_scale(self.player.important_matches)}"),
            ("Injury History", "Clean" if self.player.injury_proneness < 50 else "Concerning"),
            ("Morale", f"{self.player.morale}/100"),
            ("Development", "Improving" if self.player.age < 25 else "Stable"),
            ("Work Rate", f"{_to_100_scale(self.player.work_rate)}"),
            ("Leadership", f"{_to_100_scale(self.player.leadership)}")
        ]
        
        for i, (label, value) in enumerate(performance_notes):
            row = i // 4
            col_base = (i % 4) * 2
            
            perf_grid.grid_columnconfigure(col_base, weight=0)
            perf_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(perf_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(2, 1), pady=1
            )
            ttk.Label(perf_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
            )
        
        # Scouting notes text area - smaller
        notes_label = ttk.Label(trends_frame, text="Scouting Notes:", style='PlayerInfo.TLabel')
        notes_label.pack(anchor='w', pady=(10, 2))
        
        notes_text = tk.Text(trends_frame, width=80,  # Remove fixed height
                           bg=self.app.TITLE_BAR_COLOR, 
                           fg=self.app.TEXT_COLOR,
                           font=(self.app.FONT_FAMILY, 13),  # Increased from 9 to 13
                           wrap='word')
        notes_text.pack(fill='x', pady=(0, 5))
        
        # Insert sample scouting note
        sample_note = f"Talented {self.player.primary_position.value} with strong fundamentals. "
        if self.player.overall_rating() >= 85:
            sample_note += "Elite-level player with exceptional skills."
        elif self.player.overall_rating() >= 75:
            sample_note += "Solid NHL player with good all-around abilities."
        else:
            sample_note += "Developing player with potential."
        
        notes_text.insert('1.0', sample_note)
        notes_text.config(state='disabled')

    def _create_contract_tab(self):
        """Creates detailed contract information tab."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text='Contract')
        
        # Main container with scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Bind canvas width changes to update scrollable frame width
        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Current contract details
        self._create_current_contract_details(scrollable_frame)
        
        # Contract history
        self._create_contract_history(scrollable_frame)
        
        # Salary comparisons
        self._create_salary_comparisons(scrollable_frame)
        
        # Contract status and restrictions
        self._create_contract_status(scrollable_frame)

    def _create_current_contract_details(self, parent):
        """Creates current contract details section."""
        contract_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        contract_frame.pack(fill='x', padx=5, pady=3)
        
        ttk.Label(contract_frame, text="Current Contract", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Contract overview - 4 columns
        overview_grid = ttk.Frame(contract_frame, style='PlayerTab.TFrame')
        overview_grid.pack(fill='x', pady=(0, 10))
        
        # Calculate contract end year
        end_year = 2025 + (self.player.contract.years_remaining - 1)
        
        contract_details = [
            ("Annual Salary", f"${self.player.contract.salary:,}"),
            ("Years Remaining", f"{self.player.contract.years_remaining} years"),
            ("Contract Expires", f"July 1, {end_year}"),
            ("Signing Bonus", f"${self.player.contract.signing_bonus:,}"),
            ("Total Remaining", f"${self.player.contract.salary * self.player.contract.years_remaining:,}"),
            ("Cap Hit", f"${self.player.contract.salary:,}"),
            ("Performance Bonus", f"${getattr(self.player.contract, 'performance_bonus', 0):,}"),
            ("Contract Type", getattr(self.player.contract, 'contract_type', 'Standard'))
        ]
        
        for i, (label, value) in enumerate(contract_details):
            row = i // 4
            col_base = (i % 4) * 2
            
            overview_grid.grid_columnconfigure(col_base, weight=0)
            overview_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(overview_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(2, 1), pady=1
            )
            ttk.Label(overview_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
            )
        
        # Year-by-year breakdown
        ttk.Label(contract_frame, text="Year-by-Year Breakdown", style='PlayerInfo.TLabel').pack(anchor='w', pady=(10, 3))
        
        # Create breakdown table - more compact
        breakdown_columns = {
            'year': ('Season', 80),
            'age': ('Age', 40),
            'salary': ('Salary', 80),
            'bonus': ('Bonus', 70),
            'cap_hit': ('Cap Hit', 80),
            'status': ('Status', 60)
        }
        
        breakdown_tree = self.app._create_treeview(contract_frame, breakdown_columns)  # Remove fixed height
        breakdown_tree.pack(fill='x', pady=(0, 5))
        
        # Populate breakdown data
        current_age = self.player.age
        for year in range(self.player.contract.years_remaining):
            season_year = 2024 + year
            player_age = current_age + year
            status = "Active" if year == 0 else "Future"
            
            breakdown_tree.insert('', 'end', values=(
                f"{season_year}-{season_year+1}",
                str(player_age),
                f"${self.player.contract.salary:,}",
                f"${self.player.contract.signing_bonus if year == 0 else 0:,}",
                f"${self.player.contract.salary:,}",
                status
            ))

    def _create_contract_history(self, parent):
        """Creates contract history section."""
        history_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        history_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(history_frame, text="Contract History", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Contract history table - more compact
        history_columns = {
            'date': ('Signed', 80),
            'team': ('Team', 70),
            'years': ('Years', 50),
            'aav': ('AAV', 80),
            'total': ('Total Value', 100),
            'type': ('Type', 60)
        }
        
        history_tree = self.app._create_treeview(history_frame, history_columns)  # Remove fixed height
        history_tree.pack(fill='x')
        
        # Sample contract history (in a real game, this would be tracked)
        history_tree.insert('', 'end', values=(
            "Jul 1, 2024",
            self.player.team_name,
            str(self.player.contract.years_remaining),
            f"${self.player.contract.salary:,}",
            f"${self.player.contract.salary * self.player.contract.years_remaining:,}",
            "Standard"
        ))
        
        # Add entry level contract if player is young
        if self.player.age <= 25:
            history_tree.insert('', 'end', values=(
                "Jul 1, 2021",
                self.player.team_name,
                "3",
                "$925,000",
                "$2,775,000",
                "Entry Level"
            ))

    def _create_salary_comparisons(self, parent):
        """Creates salary comparison section."""
        comparison_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        comparison_frame.pack(fill='x', padx=5, pady=3)
        
        ttk.Label(comparison_frame, text="Salary Analysis", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Comparison grid - 4 columns
        comp_grid = ttk.Frame(comparison_frame, style='PlayerTab.TFrame')
        comp_grid.pack(fill='x')
        
        # Calculate estimated market value based on overall rating (native 1-100)
        overall = self.player.overall_rating()
        if overall >= 90:
            market_value = 10000000 + (overall - 90) * 500000   # Superstar
        elif overall >= 85:
            market_value = 7000000 + (overall - 85) * 600000    # Elite
        elif overall >= 80:
            market_value = 4500000 + (overall - 80) * 500000    # Top-line
        elif overall >= 75:
            market_value = 2500000 + (overall - 75) * 400000    # Solid NHLer
        elif overall >= 70:
            market_value = 1000000 + (overall - 70) * 300000    # Roster player
        else:
            market_value = 750000  # Depth / minimum salary
        
        # Age adjustment
        if self.player.age < 23:
            market_value *= 0.8  # Young players get less
        elif self.player.age > 32:
            market_value *= 0.7  # Older players get less
        
        market_value = int(market_value)
        
        # Position adjustment
        if self.player.primary_position == PlayerPosition.GOALIE:
            market_value *= 1.2  # Goalies get premium
        
        current_vs_market = self.player.contract.salary / market_value if market_value > 0 else 1.0
        
        comparison_data = [
            ("Current Salary", f"${self.player.contract.salary:,}"),
            ("Est. Market Value", f"${market_value:,}"),
            ("Value Rating", "Good Deal" if current_vs_market < 0.9 else "Fair" if current_vs_market < 1.1 else "Overpaid"),
            ("Team Payroll %", f"{(self.player.contract.salary / 82500000) * 100:.2f}%"),
            ("Position Avg", f"${market_value:,}"),
            ("Age Group Avg", f"${int(market_value * 0.95):,}"),
            ("Cap Efficiency", f"{current_vs_market:.2f}x"),
            ("Trade Value", "High" if current_vs_market < 1.0 else "Medium")
        ]
        
        for i, (label, value) in enumerate(comparison_data):
            row = i // 4
            col_base = (i % 4) * 2
            
            comp_grid.grid_columnconfigure(col_base, weight=0)
            comp_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(comp_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(2, 1), pady=1
            )
            
            # Color code the value rating
            if label == "Value Rating":
                if "Good Deal" in value:
                    style = "VeryGood.TLabel"
                elif "Fair" in value:
                    style = "Average.TLabel"
                else:
                    style = "Poor.TLabel"
                ttk.Label(comp_grid, text=value, style=style).grid(
                    row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
                )
            else:
                ttk.Label(comp_grid, text=value, style='PlayerValue.TLabel').grid(
                    row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
                )

    def _create_contract_status(self, parent):
        """Creates contract status and restrictions section."""
        status_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        status_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(status_frame, text="Contract Status & Restrictions", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 10))
        
        # Status grid
        status_grid = ttk.Frame(status_frame, style='PlayerTab.TFrame')
        status_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        
        # Determine waiver status
        if self.player.nhl_games_played >= 160:
            waiver_status = "Waivers Required"
        else:
            waiver_status = "Waiver Exempt"
        
        # Determine UFA/RFA status
        end_year = 2025 + (self.player.contract.years_remaining - 1)
        if self.player.age + (end_year - 2024) >= 27:
            free_agent_status = "Unrestricted Free Agent"
        else:
            free_agent_status = "Restricted Free Agent"
        
        status_data = [
            ("Waiver Status", waiver_status),
            ("Free Agency", f"{free_agent_status} ({end_year})"),
            ("Trade Restrictions", "None"),
            ("No Movement Clause", "No"),
            ("No Trade Clause", "No"),
            ("Modified No Trade", "No"),
            ("Buyout Status", "Eligible"),
            ("Expansion Draft", "Eligible")
        ]
        
        for i, (label, value) in enumerate(status_data):
            row = i // 2
            col_base = (i % 2) * 2
            
            status_grid.grid_columnconfigure(col_base, weight=0)
            status_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(status_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(5, 2), pady=2
            )
            ttk.Label(status_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(2, 15), pady=2
            )

    def _create_development_tab(self):
        """Creates player development and potential tab."""
        tab_frame = ttk.Frame(self.notebook, style='PlayerTab.TFrame')
        self.notebook.add(tab_frame, text='Development')
        
        # Main container with scrollable content
        canvas = tk.Canvas(tab_frame, bg=self.app.CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='PlayerTab.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Bind canvas width changes to update scrollable frame width
        def _configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(window_id, width=event.width)
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind("<Configure>", _configure_scroll_region)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Development overview
        self._create_development_overview(scrollable_frame)
        
        # Potential analysis
        self._create_potential_analysis(scrollable_frame)
        
        # Development history
        self._create_development_history(scrollable_frame)
        
        # Training recommendations
        self._create_training_recommendations(scrollable_frame)

    def _create_development_overview(self, parent):
        """Creates development overview section."""
        dev_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        dev_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(dev_frame, text="Development Overview", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Development grid - 4 columns
        dev_grid = ttk.Frame(dev_frame, style='PlayerTab.TFrame')
        dev_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        
        # Determine development phase
        if self.player.age <= 20:
            dev_phase = "Rapid Development"
            dev_desc = "Prime years for skill improvement"
        elif self.player.age <= 25:
            dev_phase = "Steady Growth"
            dev_desc = "Continued improvement expected"
        elif self.player.age <= 29:
            dev_phase = "Peak Years"
            dev_desc = "At or near peak performance"
        elif self.player.age <= 33:
            dev_phase = "Veteran"
            dev_desc = "Experience over physical growth"
        else:
            dev_phase = "Decline Phase"
            dev_desc = "Natural skill deterioration"
        
        # Calculate potential remaining
        potential_map = {'A+': 19, 'A': 18, 'A-': 17, 'B+': 16, 'B': 15, 'B-': 14, 'C+': 13, 'C': 12, 'C-': 11, 'D': 10, 'F': 8}
        max_potential = potential_map.get(self.player.potential_grade, 12)
        current_overall = self.player.overall_rating()
        potential_remaining = max(0, max_potential - current_overall)
        
        development_data = [
            ("Current Age", f"{self.player.age} years old"),
            ("Development Phase", dev_phase),
            ("Potential Grade", self.player.potential_grade),
            ("Current Overall", f"{_to_100_scale(current_overall)}"),
            ("Estimated Peak", f"{max(1, min(100, max_potential * 5))}"),
            ("Potential Remaining", f"{max(0, max_potential * 5 - _to_100_scale(current_overall))} points"),
            ("Development Rate", "Normal"),
            ("Years to Peak", f"{max(0, 25 - self.player.age)} years" if self.player.age < 25 else "At Peak")
        ]
        
        for i, (label, value) in enumerate(development_data):
            row = i // 4
            col_base = (i % 4) * 2
            
            dev_grid.grid_columnconfigure(col_base, weight=0)
            dev_grid.grid_columnconfigure(col_base+1, weight=1)
            
            ttk.Label(dev_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=row, column=col_base, sticky='w', padx=(2, 1), pady=1
            )
            ttk.Label(dev_grid, text=value, style='PlayerValue.TLabel').grid(
                row=row, column=col_base+1, sticky='w', padx=(1, 8), pady=1
            )
        
        # Development description - more compact
        ttk.Label(dev_frame, text="Phase Description:", style='PlayerInfo.TLabel').pack(anchor='w', pady=(8, 2))
        ttk.Label(dev_frame, text=dev_desc, style='PlayerValue.TLabel').pack(anchor='w', padx=2)

    def _create_potential_analysis(self, parent):
        """Creates potential analysis section."""
        potential_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        potential_frame.pack(fill='both', expand=True, padx=5, pady=3)  # Changed to fill both and expand
        
        ttk.Label(potential_frame, text="Potential Analysis", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Strengths and weaknesses analysis
        analysis_grid = ttk.Frame(potential_frame, style='PlayerTab.TFrame')
        analysis_grid.pack(fill='both', expand=True)  # Changed to fill both and expand
        
        # Analyze player's strongest and weakest attributes
        all_attrs = []
        if self.player.primary_position == PlayerPosition.GOALIE:
            attr_names = ['goaltending', 'reflexes', 'positioning', 'rebound_control', 'puck_handling']
        else:
            attr_names = ['skating', 'shooting', 'passing', 'checking', 'hockey_iq', 'determination', 'vision', 'composure']
        
        for attr_name in attr_names:
            value = getattr(self.player, attr_name, 10)
            all_attrs.append((attr_name.replace('_', ' ').title(), value))
        
        # Sort by value to find strengths and weaknesses
        all_attrs.sort(key=lambda x: x[1], reverse=True)
        
        strengths = all_attrs[:3]  # Top 3
        weaknesses = all_attrs[-3:]  # Bottom 3
        
        # Display strengths
        ttk.Label(analysis_grid, text="Key Strengths:", style='PlayerInfo.TLabel').grid(
            row=0, column=0, sticky='w', padx=5, pady=(0, 5)
        )
        
        for i, (attr, value) in enumerate(strengths):
            style, text = self._get_attribute_style_and_text(value)
            ttk.Label(analysis_grid, text=f"• {attr}: {text}", style='PlayerValue.TLabel').grid(
                row=i+1, column=0, sticky='w', padx=15, pady=1
            )
        
        # Display weaknesses
        ttk.Label(analysis_grid, text="Areas for Improvement:", style='PlayerInfo.TLabel').grid(
            row=0, column=1, sticky='w', padx=25, pady=(0, 5)
        )
        
        for i, (attr, value) in enumerate(weaknesses):
            style, text = self._get_attribute_style_and_text(value)
            ttk.Label(analysis_grid, text=f"• {attr}: {text}", style='PlayerValue.TLabel').grid(
                row=i+1, column=1, sticky='w', padx=35, pady=1
            )
        
        analysis_grid.grid_columnconfigure(0, weight=1)
        analysis_grid.grid_columnconfigure(1, weight=1)

    def _create_development_history(self, parent):
        """Creates development history section."""
        history_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        history_frame.pack(fill='x', padx=5, pady=3)
        
        ttk.Label(history_frame, text="Development History", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Development history table - more compact
        history_columns = {
            'season': ('Season', 70),
            'age': ('Age', 40),
            'overall': ('Overall', 60),
            'key_improvement': ('Key Improvement', 120),
            'notes': ('Notes', 150)
        }
        
        history_tree = self.app._create_treeview(history_frame, history_columns)  # Remove fixed height
        history_tree.pack(fill='x')
        
        # Sample development history (in a real game, this would be tracked)
        current_age = self.player.age
        current_overall = self.player.overall_rating()
        
        # Generate historical data
        for i in range(min(4, current_age - 18)):
            season_year = 2024 - i
            age = current_age - i
            # Simulate lower overall ratings in the past
            past_overall = max(8, current_overall - (i * 2) - (1 if i > 0 else 0))
            
            if i == 0:
                improvement = "Current Season"
                notes = "Active development"
            else:
                improvements = ["Skating", "Shooting", "Hockey IQ", "Passing", "Checking", "Vision"]
                improvement = improvements[i % len(improvements)]
                notes = f"Improved {improvement.lower()}"
            
            history_tree.insert('', 'end', values=(
                f"{season_year}-{season_year+1}",
                str(age),
                f"{_to_100_scale(past_overall)}",
                improvement,
                notes
            ))

    def _create_training_recommendations(self, parent):
        """Creates training recommendations section."""
        training_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=8)
        training_frame.pack(fill='x', padx=5, pady=3)
        
        ttk.Label(training_frame, text="Training Recommendations", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 5))
        
        # Priority training areas - more compact
        priority_grid = ttk.Frame(training_frame, style='PlayerTab.TFrame')
        priority_grid.pack(fill='x', pady=(0, 8))
        
        # Determine training priorities based on position and weaknesses
        if self.player.primary_position == PlayerPosition.GOALIE:
            training_priorities = [
                ("High Priority", "Positioning", "Critical for goaltending success"),
                ("High Priority", "Rebound Control", "Reduce second-chance opportunities"),
                ("Medium Priority", "Reflexes", "Natural ability, limited improvement"),
                ("Low Priority", "Puck Handling", "Situational skill development")
            ]
        else:
            # Find areas that need improvement
            low_skills = []
            if self.player.skating < 12:
                low_skills.append(("High Priority", "Skating", "Foundation for all other skills"))
            if self.player.hockey_iq < 12:
                low_skills.append(("High Priority", "Hockey IQ", "Critical for decision making"))
            if self.player.shooting < 12:
                low_skills.append(("Medium Priority", "Shooting", "Essential for scoring"))
            if self.player.passing < 12:
                low_skills.append(("Medium Priority", "Passing", "Team play improvement"))
            
            # Default recommendations if all skills are decent
            if not low_skills:
                training_priorities = [
                    ("High Priority", "Hockey IQ", "Always room for improvement"),
                    ("Medium Priority", "Vision", "Enhance playmaking ability"),
                    ("Medium Priority", "Composure", "Better under pressure"),
                    ("Low Priority", "Leadership", "Character development")
                ]
            else:
                training_priorities = low_skills[:4]  # Top 4 priorities
        
        # Create training recommendations table
        training_columns = {
            'priority': ('Priority', 80),
            'skill': ('Skill Area', 120),
            'description': ('Description', 250),
            'timeline': ('Timeline', 80)
        }
        
        training_tree = self.app._create_treeview(training_frame, training_columns)  # Remove fixed height
        training_tree.pack(fill='x')
        
        # Populate training recommendations
        timelines = ["Immediate", "3-6 months", "6-12 months", "Long-term"]
        for i, (priority, skill, description) in enumerate(training_priorities):
            timeline = timelines[i % len(timelines)]
            training_tree.insert('', 'end', values=(priority, skill, description, timeline))
        
        # Development tips
        tips_label = ttk.Label(training_frame, text="Development Tips:", style='PlayerInfo.TLabel')
        tips_label.pack(anchor='w', pady=(15, 5))
        
        tips_text = tk.Text(training_frame, width=80,  # Remove fixed height
                          bg=self.app.TITLE_BAR_COLOR,
                          fg=self.app.TEXT_COLOR,
                          font=(self.app.FONT_FAMILY, 13),  # Increased from 9 to 13
                          wrap='word')
        tips_text.pack(fill='x', pady=(0, 5))
        
        # Generate development tips based on age and potential
        if self.player.age <= 22:
            tips = "Focus on fundamental skills and game experience. Young players develop quickly with proper guidance. Consider AHL assignment for regular playing time if not ready for NHL."
        elif self.player.age <= 27:
            tips = "Prime development years. Focus on refining existing skills and adding new dimensions to gameplay. Mental aspects become increasingly important."
        else:
            tips = "Veteran player development focuses on maintaining current abilities and tactical improvements. Leadership and mentoring roles become valuable."
        
        tips_text.insert('1.0', tips)
        tips_text.config(state='disabled')

    # NOTE: _create_enhanced_basic_info was removed -- personal details now
    # live on the Personality tab via _personal_details_items() /
    # _create_personal_details_section().

    def _create_physical_attributes(self, parent, row=1):
        """Creates physical attributes section."""
        phys_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        phys_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(phys_frame, text="Physical Attributes", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        phys_grid = ttk.Frame(phys_frame, style='PlayerTab.TFrame')
        phys_grid.pack(fill='both', expand=True)
        phys_grid.grid_columnconfigure(0, weight=0)
        phys_grid.grid_columnconfigure(1, weight=1)
        phys_grid.grid_columnconfigure(2, weight=0)
        
        # Physical attributes with visual bars
        physical_attrs = [
            ("Strength", getattr(self.player, 'strength', 10)),
            ("Speed", getattr(self.player, 'speed', 10)),
            ("Agility", getattr(self.player, 'agility', 10)),
            ("Acceleration", getattr(self.player, 'acceleration', 10)),
            ("Balance", getattr(self.player, 'balance', 10)),
            ("Stamina", getattr(self.player, 'stamina', 10)),
            ("Durability", 100 - getattr(self.player, 'injury_proneness', 50)),
        ]
        
        for i, (label, value) in enumerate(physical_attrs):
            ttk.Label(phys_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            
            # Create mini progress bar for visual representation
            bar_frame = ttk.Frame(phys_grid, style='PlayerTab.TFrame')
            bar_frame.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=3)
            
            bar_canvas = tk.Canvas(bar_frame, width=120, height=16, bg=self.app.CONTENT_BG, highlightthickness=0)
            bar_canvas.pack(fill='x')
            
            # Draw attribute bar
            bar_width = int((min(value, 100) / 100) * 110)
            bar_color = self._get_rating_color(value)
            bar_canvas.create_rectangle(5, 3, 5+bar_width, 13, fill=bar_color, outline=bar_color)
            bar_canvas.create_rectangle(3, 1, 117, 15, outline=self.app.TEXT_COLOR, width=1)
            
            ttk.Label(phys_grid, text=str(_to_100_scale(value)), style='PlayerInfo.TLabel', anchor='center', width=8).grid(
                row=i, column=2, padx=(5, 0), pady=3
            )

    def _create_injury_history(self, parent, row=2):
        """Creates injury history section."""
        injury_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        injury_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(injury_frame, text="Health & Durability", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        health_grid = ttk.Frame(injury_frame, style='PlayerTab.TFrame')
        health_grid.pack(fill='both', expand=True)
        health_grid.grid_columnconfigure(0, weight=0)
        health_grid.grid_columnconfigure(1, weight=1)
        
        # Health information
        injury_prone = getattr(self.player, 'injury_proneness', 50)
        durability = 100 - injury_prone
        
        health_info = [
            ("Injury Proneness:", f"{injury_prone}/100 ({'Low' if injury_prone <= 25 else 'Medium' if injury_prone <= 55 else 'High'})"),
            ("Current Health:", "100%" if not getattr(self.player, 'is_injured', False) else "Injured"),
            ("Days Missed (Season):", f"{getattr(self.player, 'days_missed', 0)} days"),
            ("Career Games Missed:", f"{getattr(self.player, 'career_games_missed', 0)} games"),
            ("Last Injury:", f"{getattr(self.player, 'last_injury', 'None')}"),
        ]
        
        for i, (label, value) in enumerate(health_info):
            ttk.Label(health_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(health_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_career_progression(self, parent, row=3):
        """Creates career progression section."""
        career_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        career_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(career_frame, text="Career Progression", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        career_grid = ttk.Frame(career_frame, style='PlayerTab.TFrame')
        career_grid.pack(fill='both', expand=True)
        career_grid.grid_columnconfigure(0, weight=0)
        career_grid.grid_columnconfigure(1, weight=1)
        
        # Career milestones and progression
        career_info = [
            ("Professional Debut:", f"{getattr(self.player, 'pro_debut', 'This Season')}"),
            ("Teams Played For:", f"{getattr(self.player, 'teams_count', 1)} teams"),
            ("Current Team Since:", f"{getattr(self.player, 'team_tenure', 'This season')}"),
            ("Career Peak Rating:", f"{getattr(self.player, 'peak_rating', 15)}/20"),
            ("Development Status:", self._get_development_status()),
            ("Potential Rating:", f"{getattr(self.player, 'potential', 'Unknown')}/20"),
        ]
        
        for i, (label, value) in enumerate(career_info):
            ttk.Label(career_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(career_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_accolades(self, parent, row=2):
        """Permanent trophy case: grouped, de-duplicated award wins.

        Format (Muck's spec):
            Hart Trophy Winner: 2021, 2025
            Stanley Cup Winner: 2021-22, 2022-23
        """
        acc_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        acc_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))

        ttk.Label(acc_frame, text="🏆 Accolades",
                  style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))

        try:
            import accolades as _acc
            grouped = _acc.group_accolades(self.player)
        except Exception:
            grouped = []
        if not grouped:
            ttk.Label(acc_frame, text="No awards yet.",
                      style='PlayerInfo.TLabel').pack(anchor='w')
            return
        for label, years in grouped:
            ttk.Label(acc_frame, text=f"{label} Winner: {', '.join(years)}",
                      style='PlayerValue.TLabel').pack(anchor='w')

    def _create_career_moments(self, parent, row=4):
        """Signature single-game performances (hat tricks, shutouts,
        40-save nights...). The game log that keeps a kid's huge night
        from being forgotten when he's the next man up or a trade chip."""
        moments_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        moments_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))

        ttk.Label(moments_frame, text="Signature Games",
                  style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))

        moments = getattr(self.player, 'career_moments', None) or []
        moments = [m for m in moments if isinstance(m, dict)]
        # Newest first.
        moments = sorted(moments, key=lambda m: m.get("date", ""),
                         reverse=True)

        _emoji = {"hat_trick": "🎩", "four_point": "⭐", "five_point": "🌟",
                  "shutout": "🧱", "forty_saves": "🥅", "steal": "🥅"}
        if not moments:
            ttk.Label(moments_frame, text="No signature games yet.",
                      style='PlayerInfo.TLabel').pack(anchor='w')
            return
        for m in moments[:6]:
            emo = _emoji.get(m.get("kind", ""), "🏒")
            date_s = m.get("date", "")
            label = m.get("label", "Big night")
            detail = m.get("detail", "")
            line1 = f"{emo} {label} — {date_s}"
            if m.get("playoff"):
                line1 += " (playoffs)"
            ttk.Label(moments_frame, text=line1,
                      style='PlayerValue.TLabel').pack(anchor='w')
            if detail:
                ttk.Label(moments_frame, text=f"    {detail}",
                          style='PlayerInfo.TLabel').pack(anchor='w')
        if len(moments) > 6:
            ttk.Label(
                moments_frame,
                text=f"+ {len(moments) - 6} more signature "
                     f"{'game' if len(moments) == 7 else 'games'} on record.",
                style='PlayerInfo.TLabel').pack(anchor='w', pady=(4, 0))

    def _create_enhanced_key_attributes(self, parent, row=0):
        """Creates enhanced key attributes section with visual bars."""
        attr_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        attr_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(attr_frame, text="Key Attributes", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        # Get key attributes based on position
        if self.player.primary_position == PlayerPosition.GOALIE:
            key_attrs = [
                ("Goaltending", self.player.goaltending),
                ("Reflexes", self.player.reflexes),
                ("Positioning", self.player.positioning),
                ("Rebound Control", self.player.rebound_control),
                ("Puck Handling", self.player.puck_handling),
                ("Composure", self.player.composure),
                ("Consistency", getattr(self.player, 'consistency', 10)),
                ("Anticipation", getattr(self.player, 'anticipation', 10)),
            ]
        else:
            key_attrs = [
                ("Skating", self.player.skating),
                ("Shooting", self.player.shooting),
                ("Passing", self.player.passing),
                ("Puck Handling", self.player.puck_handling),
                ("Checking", self.player.checking),
                ("Hockey IQ", self.player.hockey_iq),
                ("Determination", self.player.determination),
                ("Teamwork", self.player.teamwork),
            ]
        
        attr_grid = ttk.Frame(attr_frame, style='PlayerTab.TFrame')
        attr_grid.pack(fill='both', expand=True)
        attr_grid.grid_columnconfigure(0, weight=0)
        attr_grid.grid_columnconfigure(1, weight=1)
        attr_grid.grid_columnconfigure(2, weight=0)
        
        for i, (label, value) in enumerate(key_attrs):
            ttk.Label(attr_grid, text=f"{label}:", style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            
            # Create attribute bar
            bar_frame = ttk.Frame(attr_grid, style='PlayerTab.TFrame')
            bar_frame.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=3)
            
            bar_canvas = tk.Canvas(bar_frame, width=120, height=20, bg=self.app.CONTENT_BG, highlightthickness=0)
            bar_canvas.pack(fill='x')
            
            # Draw enhanced attribute bar with gradient effect
            bar_width = int((min(value, 100) / 100) * 110)
            bar_color = self._get_rating_color(value)
            bar_canvas.create_rectangle(5, 4, 5+bar_width, 16, fill=bar_color, outline=bar_color)
            bar_canvas.create_rectangle(3, 2, 117, 18, outline=self.app.TEXT_COLOR, width=1)
            
            # Add value text
            style, text = self._get_attribute_style_and_text(value)
            ttk.Label(attr_grid, text=str(_to_100_scale(value)), style='PlayerInfo.TLabel', anchor='center', width=8).grid(
                row=i, column=2, padx=(5, 0), pady=3
            )

    def _create_performance_metrics(self, parent, row=1):
        """Creates performance metrics section."""
        perf_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        perf_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(perf_frame, text="Season Performance", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        stats_grid = ttk.Frame(perf_frame, style='PlayerTab.TFrame')
        stats_grid.pack(fill='both', expand=True)
        stats_grid.grid_columnconfigure(0, weight=0)
        stats_grid.grid_columnconfigure(1, weight=1)
        
        # Get performance stats
        if self.player.primary_position == PlayerPosition.GOALIE:
            performance_stats = [
                ("Games Played:", f"{getattr(self.player, 'games_played', 0)}"),
                ("Wins:", f"{getattr(self.player, 'wins', 0)}"),
                ("Losses:", f"{getattr(self.player, 'losses', 0)}"),
                ("Save %:", f"{getattr(self.player, 'save_percentage', 0.000):.3f}"),
                ("GAA:", f"{getattr(self.player, 'goals_against_avg', 0.00):.2f}"),
                ("Shutouts:", f"{getattr(self.player, 'shutouts', 0)}"),
            ]
        else:
            performance_stats = [
                ("Games Played:", f"{getattr(self.player, 'games_played', 0)}"),
                ("Goals:", f"{getattr(self.player, 'goals', 0)}"),
                ("Assists:", f"{getattr(self.player, 'assists', 0)}"),
                ("Points:", f"{getattr(self.player, 'points', 0)}"),
                ("Plus/Minus:", f"{getattr(self.player, 'plus_minus', 0):+d}"),
                ("TOI/Game:", f"{getattr(self.player, 'avg_toi', '0:00')}"),
            ]
        
        for i, (label, value) in enumerate(performance_stats):
            ttk.Label(stats_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(stats_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_skill_development(self, parent, row=2):
        """Creates skill development tracking section."""
        dev_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        dev_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(dev_frame, text="Development Tracking", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        dev_grid = ttk.Frame(dev_frame, style='PlayerTab.TFrame')
        dev_grid.pack(fill='both', expand=True)
        dev_grid.grid_columnconfigure(0, weight=0)
        dev_grid.grid_columnconfigure(1, weight=1)
        
        development_info = [
            ("Age Group:", self._get_age_group()),
            ("Development Phase:", self._get_development_status()),
            ("Training Focus:", self._get_training_focus()),
            ("Coachability:", f"{_to_100_scale(getattr(self.player, 'coachability', 25))}"),
            ("Work Ethic:", f"{_to_100_scale(getattr(self.player, 'work_ethic', 25))}"),
            ("Learning Rate:", self._get_learning_rate()),
        ]
        
        for i, (label, value) in enumerate(development_info):
            ttk.Label(dev_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(dev_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_team_chemistry(self, parent, row=3):
        """Creates team chemistry and relationships section."""
        chem_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        chem_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(chem_frame, text="Team Integration", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        chem_grid = ttk.Frame(chem_frame, style='PlayerTab.TFrame')
        chem_grid.pack(fill='both', expand=True)
        chem_grid.grid_columnconfigure(0, weight=0)
        chem_grid.grid_columnconfigure(1, weight=1)
        
        chemistry_info = [
            ("Team Chemistry:", f"{getattr(self.player, 'team_chemistry', 15)}/20"),
            ("Leadership:", f"{_to_100_scale(getattr(self.player, 'leadership', 10))}"),
            ("Locker Room Presence:", self._get_locker_room_presence()),
            ("Mentorship Value:", self._get_mentorship_value()),
            ("Line Chemistry:", f"{getattr(self.player, 'line_chemistry', 15)}/20"),
            ("Adaptability:", f"{_to_100_scale(getattr(self.player, 'adaptability', 25))}"),
        ]
        
        for i, (label, value) in enumerate(chemistry_info):
            ttk.Label(chem_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(chem_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_enhanced_contract_info(self, parent, row=0):
        """Creates enhanced contract information section."""
        contract_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        contract_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(contract_frame, text="Contract Details", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        contract_grid = ttk.Frame(contract_frame, style='PlayerTab.TFrame')
        contract_grid.pack(fill='both', expand=True)
        contract_grid.grid_columnconfigure(0, weight=0)
        contract_grid.grid_columnconfigure(1, weight=1)
        
        if hasattr(self.player, 'contract') and self.player.contract:
            contract_info = [
                ("Contract Type:", f"{getattr(self.player.contract, 'contract_type', 'Standard')}"),
                ("Years Remaining:", f"{getattr(self.player.contract, 'years_left', 0)} years"),
                ("Annual Salary:", f"${getattr(self.player.contract, 'salary', 750000):,}"),
                ("Total Value:", f"${getattr(self.player.contract, 'total_value', 750000):,}"),
                ("Signing Bonus:", f"${getattr(self.player.contract, 'signing_bonus', 0):,}"),
                ("Trade Clauses:", f"{getattr(self.player.contract, 'trade_clauses', 'None')}"),
                ("Cap Hit:", f"${getattr(self.player.contract, 'cap_hit', 750000):,}"),
                ("Expires:", f"{getattr(self.player.contract, 'expiry_year', 'Unknown')}"),
            ]
        else:
            contract_info = [
                ("Contract Status:", "No Active Contract"),
                ("RFA/UFA Status:", self._get_free_agent_status()),
                ("Qualifying Offer:", "N/A"),
                ("Arbitration Rights:", "N/A"),
                ("Entry Level Eligible:", "Unknown"),
                ("Waivers Required:", "Yes" if self.player.nhl_games_played >= 160 else "No"),
            ]
        
        for i, (label, value) in enumerate(contract_info):
            ttk.Label(contract_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(contract_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_market_value_info(self, parent, row=1):
        """Creates market value and trade information section."""
        market_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        market_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(market_frame, text="Market Value", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        market_grid = ttk.Frame(market_frame, style='PlayerTab.TFrame')
        market_grid.pack(fill='both', expand=True)
        market_grid.grid_columnconfigure(0, weight=0)
        market_grid.grid_columnconfigure(1, weight=1)
        
        # Calculate estimated market value based on attributes
        estimated_value = self._calculate_market_value()
        
        market_info = [
            ("Estimated Value:", f"${estimated_value:,}"),
            ("Trade Value:", self._get_trade_value()),
            ("Comparables:", self._get_comparable_players()),
            ("Market Demand:", self._get_market_demand()),
            ("Age Factor:", self._get_age_factor()),
            ("Position Scarcity:", self._get_position_scarcity()),
        ]
        
        for i, (label, value) in enumerate(market_info):
            ttk.Label(market_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(market_grid, text=str(value), style='PlayerInfo.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )

    def _create_scouting_report(self, parent, row=2):
        """Creates scouting report section."""
        scout_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        scout_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(scout_frame, text="Scouting Report", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        # Scouting report text area
        report_text = tk.Text(scout_frame, height=8, width=30, bg=self.app.CONTENT_BG, 
                             fg=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 11),
                             wrap='word', relief='sunken', borderwidth=1)
        report_text.pack(fill='both', expand=True)
        
        # Generate scouting report
        report = self._generate_scouting_report()
        report_text.insert('1.0', report)
        report_text.config(state='disabled')

    def _create_coaching_notes(self, parent, row=3):
        """Creates coaching notes and recommendations section."""
        notes_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        notes_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(notes_frame, text="Coaching Notes", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        # Coaching notes text area
        notes_text = tk.Text(notes_frame, height=8, width=30, bg=self.app.CONTENT_BG,
                            fg=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 11),
                            wrap='word', relief='sunken', borderwidth=1)
        notes_text.pack(fill='both', expand=True)
        
        # Generate coaching recommendations
        notes = self._generate_coaching_notes()
        notes_text.insert('1.0', notes)
        notes_text.config(state='disabled')

    # Helper methods for the enhanced sections
    def _get_development_status(self):
        """Determines the player's development status based on age."""
        age = self.player.age
        if age <= 20:
            return "Developing Prospect"
        elif age <= 25:
            return "Rising Player"
        elif age <= 29:
            return "Prime Years"
        elif age <= 33:
            return "Veteran"
        else:
            return "Declining"

    def _get_age_group(self):
        """Returns the player's age group classification."""
        age = self.player.age
        if age <= 21:
            return "Junior/Entry Level"
        elif age <= 25:
            return "Young Professional"
        elif age <= 30:
            return "Prime Years"
        else:
            return "Veteran"

    def _get_training_focus(self):
        """Suggests training focus based on player attributes."""
        if self.player.primary_position == PlayerPosition.GOALIE:
            if self.player.reflexes < 12:
                return "Reflexes & Positioning"
            elif self.player.positioning < 12:
                return "Positioning & Angles"
            else:
                return "Mental Game & Consistency"
        else:
            if self.player.skating < 12:
                return "Skating & Mobility"
            elif self.player.hockey_iq < 60:
                return "Hockey IQ & Vision"
            else:
                return "Skill Refinement"

    def _get_learning_rate(self):
        """Calculates learning rate based on age and attributes."""
        base_rate = max(1, 21 - self.player.age) * 5  # Younger players learn faster
        coachability = _to_20_scale(getattr(self.player, 'coachability', 25))
        work_ethic = _to_20_scale(getattr(self.player, 'work_ethic', 25))
        
        rate = (base_rate + coachability + work_ethic) / 3
        if rate >= 15:
            return "Very High"
        elif rate >= 12:
            return "High"
        elif rate >= 9:
            return "Average"
        else:
            return "Low"

    def _get_locker_room_presence(self):
        """Determines locker room presence."""
        leadership = getattr(self.player, 'leadership', 10)
        if leadership >= 75:
            return "Team Leader"
        elif leadership >= 60:
            return "Positive Influence"
        elif leadership >= 45:
            return "Neutral"
        else:
            return "Needs Guidance"

    def _get_mentorship_value(self):
        """Calculates mentorship value for younger players."""
        if self.player.age >= 30:
            leadership = getattr(self.player, 'leadership', 10)
            experience = min(self.player.age - 18, 15)
            value = (leadership + experience) / 2
            if value >= 15:
                return "Excellent Mentor"
            elif value >= 12:
                return "Good Mentor"
            else:
                return "Limited"
        else:
            return "Too Young"

    def _get_free_agent_status(self):
        """Determines free agent status."""
        if self.player.age <= 25:
            return "RFA Eligible"
        else:
            return "UFA Eligible"

    def _calculate_market_value(self):
        """Calculates estimated market value."""
        base_value = self.player.overall_rating() * 200000
        age_factor = max(0.5, (35 - self.player.age) / 15)
        return int(base_value * age_factor)

    def _get_trade_value(self):
        """Determines trade value classification."""
        value = self._calculate_market_value()
        if value >= 8000000:
            return "Premium Asset"
        elif value >= 4000000:
            return "High Value"
        elif value >= 2000000:
            return "Solid Asset"
        else:
            return "Depth Player"

    def _get_comparable_players(self):
        """Returns comparable player description."""
        overall = self.player.overall_rating()
        position = self.player.primary_position.value
        
        if overall >= 18:
            return f"Elite {position}"
        elif overall >= 16:
            return f"Star {position}"
        elif overall >= 14:
            return f"Top 6 {position}" if position != "G" else "Starting Goalie"
        elif overall >= 11:
            return f"Middle 6 {position}" if position != "G" else "Backup Goalie"
        else:
            return f"Depth {position}"

    def _get_market_demand(self):
        """Determines market demand."""
        if self.player.primary_position == PlayerPosition.GOALIE:
            return "Moderate" if self.player.overall_rating() >= 14 else "Low"
        elif self.player.primary_position.value in ["C", "D"]:
            return "High" if self.player.overall_rating() >= 14 else "Moderate"
        else:
            return "Moderate" if self.player.overall_rating() >= 16 else "Low"

    def _get_age_factor(self):
        """Calculates age impact on value."""
        age = self.player.age
        if age <= 23:
            return "Prime Development"
        elif age <= 28:
            return "Peak Years"
        elif age <= 32:
            return "Declining Value"
        else:
            return "Limited Asset"

    def _get_position_scarcity(self):
        """Determines position scarcity."""
        position_scarcity = {
            "G": "High",
            "C": "Very High", 
            "LW": "Moderate",
            "RW": "Moderate",
            "D": "High"
        }
        return position_scarcity.get(self.player.primary_position.value, "Moderate")

    def _generate_scouting_report(self):
        """Generates a comprehensive scouting report."""
        overall = self.player.overall_rating()
        position = self.player.primary_position.value
        age = self.player.age
        
        # Base assessment
        if overall >= 18:
            assessment = f"Elite {position} with exceptional abilities across all areas."
        elif overall >= 16:
            assessment = f"Star-quality {position} with excellent skills and high impact potential."
        elif overall >= 14:
            assessment = f"Strong {position} who can contribute significantly at the professional level."
        elif overall >= 11:
            assessment = f"Solid {position} with reliable abilities and room for development."
        else:
            assessment = f"Developing {position} who needs time and coaching to reach potential."
        
        # Age consideration
        if age <= 22:
            age_note = " Strong development potential with proper guidance and experience."
        elif age <= 27:
            age_note = " In prime development phase with room for skill enhancement."
        elif age <= 32:
            age_note = " Experienced player who brings veteran leadership and consistency."
        else:
            age_note = " Veteran presence who can provide mentorship and depth."
        
        # Position-specific notes
        if self.player.primary_position == PlayerPosition.GOALIE:
            if self.player.reflexes >= 16:
                position_note = " Exceptional reflexes and positioning make this goalie a game-changer."
            elif self.player.positioning >= 14:
                position_note = " Strong positional play and technical fundamentals."
            else:
                position_note = " Needs work on technical aspects but shows potential."
        else:
            if self.player.skating >= 16:
                position_note = " Excellent skating ability creates opportunities and defensive value."
            elif self.player.hockey_iq >= 14:
                position_note = " High hockey IQ compensates for physical limitations."
            else:
                position_note = " Solid fundamentals with room for skill development."
        
        return assessment + age_note + position_note

    def _generate_coaching_notes(self):
        """Generates coaching recommendations."""
        recommendations = []
        
        # Development recommendations based on age
        if self.player.age <= 23:
            recommendations.append("• Focus on fundamental skill development and game experience")
            recommendations.append("• Regular playing time crucial for continued growth")
            recommendations.append("• Pair with veteran mentors for guidance")
        elif self.player.age <= 28:
            recommendations.append("• Refine existing skills and add new dimensions to game")
            recommendations.append("• Increase leadership responsibilities")
            recommendations.append("• Focus on tactical understanding and game management")
        else:
            recommendations.append("• Utilize experience for mentoring younger players")
            recommendations.append("• Manage ice time to preserve effectiveness")
            recommendations.append("• Focus on tactical roles and special situations")
        
        # Position-specific recommendations
        if self.player.primary_position == PlayerPosition.GOALIE:
            if self.player.positioning < 14:
                recommendations.append("• Work extensively on positioning and angle play")
            if self.player.rebound_control < 12:
                recommendations.append("• Improve rebound control techniques")
            recommendations.append("• Mental preparation and game management are key")
        else:
            if self.player.skating < 14:
                recommendations.append("• Prioritize skating drills and edge work")
            if self.player.hockey_iq < 12:
                recommendations.append("• Video study and tactical training essential")
            if self.player.teamwork < 12:
                recommendations.append("• Emphasize team concepts and system play")
        
        return "\n".join(recommendations)

    def _create_player_comparison(self, parent, row=4):
        """Creates player comparison section with league averages and similar players."""
        comp_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        comp_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(comp_frame, text="Player Comparison", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        # Create comparison grid
        comp_grid = ttk.Frame(comp_frame, style='PlayerTab.TFrame')
        comp_grid.pack(fill='both', expand=True)
        comp_grid.grid_columnconfigure(0, weight=0)
        comp_grid.grid_columnconfigure(1, weight=1)
        comp_grid.grid_columnconfigure(2, weight=1)
        
        # Headers
        ttk.Label(comp_grid, text="Attribute", style='PlayerSubheader.TLabel').grid(
            row=0, column=0, sticky='w', padx=(0, 10), pady=2
        )
        ttk.Label(comp_grid, text="Player", style='PlayerSubheader.TLabel').grid(
            row=0, column=1, pady=2
        )
        ttk.Label(comp_grid, text="League Avg", style='PlayerSubheader.TLabel').grid(
            row=0, column=2, pady=2
        )
        
        # Key comparison attributes
        if self.player.primary_position == PlayerPosition.GOALIE:
            comp_attrs = [
                ("Reflexes", self.player.reflexes, 13),
                ("Positioning", self.player.positioning, 12),
                ("Rebound Control", self.player.rebound_control, 11),
                ("Overall Rating", self.player.overall_rating(), 12)
            ]
        else:
            comp_attrs = [
                ("Skating", self.player.skating, 13),
                ("Shooting", self.player.shooting, 12),
                ("Passing", self.player.passing, 12),
                ("Hockey IQ", self.player.hockey_iq, 13),
                ("Overall Rating", self.player.overall_rating(), 12)
            ]
        
        for i, (attr_name, player_val, league_avg) in enumerate(comp_attrs, 1):
            ttk.Label(comp_grid, text=f"{attr_name}:", style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=2
            )
            
            # Player value with color coding
            player_color = self._get_comparison_color(player_val, league_avg)
            player_label = ttk.Label(comp_grid, text=str(_to_100_scale(player_val)), style='PlayerInfo.TLabel')
            player_label.grid(row=i, column=1, pady=2)
            
            ttk.Label(comp_grid, text=str(_to_100_scale(league_avg)), style='PlayerInfo.TLabel').grid(
                row=i, column=2, pady=2
            )
        
        # Similar players section
        similar_frame = ttk.Frame(comp_frame, style='PlayerTab.TFrame')
        similar_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(similar_frame, text="Similar Players:", style='PlayerInfo.TLabel').pack(anchor='w')
        similar_players = self._get_similar_players()
        ttk.Label(similar_frame, text=similar_players, style='PlayerValue.TLabel', 
                 wraplength=250).pack(anchor='w', pady=(2, 0))

    def _create_advanced_analytics(self, parent, row=5):
        """Creates advanced analytics and metrics section."""
        analytics_frame = ttk.Frame(parent, style='PlayerPanel.TFrame', padding=10)
        analytics_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 5))
        
        ttk.Label(analytics_frame, text="Advanced Analytics", style='PlayerSubheader.TLabel').pack(anchor='w', pady=(0, 8))
        
        # Create analytics grid
        analytics_grid = ttk.Frame(analytics_frame, style='PlayerTab.TFrame')
        analytics_grid.pack(fill='both', expand=True)
        analytics_grid.grid_columnconfigure(0, weight=0)
        analytics_grid.grid_columnconfigure(1, weight=1)
        
        # Advanced metrics
        overall = self.player.overall_rating()
        
        analytics_data = [
            ("Efficiency Rating:", f"{self._calculate_efficiency_rating():.1f}"),
            ("Versatility Score:", f"{self._calculate_versatility_score():.1f}"),
            ("Consistency Index:", f"{self._calculate_consistency_index():.1f}"),
            ("Development Potential:", f"{self._calculate_development_potential():.1f}"),
            ("Injury Risk Factor:", f"{self._calculate_injury_risk():.1f}"),
            ("Team Chemistry Impact:", f"{self._calculate_chemistry_impact():.1f}"),
        ]
        
        for i, (label, value) in enumerate(analytics_data):
            ttk.Label(analytics_grid, text=label, style='PlayerInfo.TLabel').grid(
                row=i, column=0, sticky='w', padx=(0, 10), pady=3
            )
            ttk.Label(analytics_grid, text=value, style='PlayerValue.TLabel').grid(
                row=i, column=1, sticky='w', pady=3
            )
        
        # Visual performance radar
        radar_frame = ttk.Frame(analytics_frame, style='PlayerTab.TFrame')
        radar_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(radar_frame, text="Performance Profile:", style='PlayerInfo.TLabel').pack(anchor='w')
        
        # Create a simple text-based radar chart
        radar_canvas = tk.Canvas(radar_frame, width=250, height=120, bg=self.app.CONTENT_BG, 
                                highlightthickness=1, highlightcolor=self.app.TEXT_COLOR)
        radar_canvas.pack(pady=(5, 0))
        
        self._draw_performance_profile(radar_canvas)

    def _get_comparison_color(self, player_val, league_avg):
        """Returns color for comparison values."""
        if player_val >= league_avg + 3:
            return "#4CAF50"  # Green for well above average
        elif player_val >= league_avg + 1:
            return "#8BC34A"  # Light green for above average
        elif player_val >= league_avg - 1:
            return "#FFC107"  # Yellow for average
        else:
            return "#FF9800"  # Orange for below average

    def _get_similar_players(self):
        """Returns names of similar players based on attributes and position."""
        # This would ideally compare against other players in the league
        # For now, return position-based examples
        if self.player.primary_position == PlayerPosition.GOALIE:
            examples = ["Elite Netminder", "Solid Starter", "Backup Option"]
        elif self.player.primary_position == PlayerPosition.CENTER:
            examples = ["Playmaking Center", "Two-Way Forward", "Scoring Threat"]
        elif self.player.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            examples = ["Sniper", "Power Forward", "Checking Winger"]
        else:  # Defense
            examples = ["Offensive Defenseman", "Stay-at-Home D", "Two-Way Defender"]
        
        overall = self.player.overall_rating()
        if overall >= 16:
            return f"Elite {examples[0]}"
        elif overall >= 13:
            return f"Good {examples[1]}"
        else:
            return f"Developing {examples[2]}"

    def _calculate_efficiency_rating(self):
        """Calculate efficiency rating based on overall performance vs expectations."""
        overall = self.player.overall_rating()
        age = self.player.age
        
        # Adjust for age expectations
        if age <= 22:
            expected = 10  # Young players expected to be developing
        elif age <= 27:
            expected = 13  # Prime years
        elif age <= 32:
            expected = 14  # Peak years
        else:
            expected = 11  # Declining years
        
        return min(10.0, max(1.0, (overall / expected) * 5.0))

    def _calculate_versatility_score(self):
        """Calculate how versatile the player is across different skills."""
        if self.player.primary_position == PlayerPosition.GOALIE:
            attrs = [self.player.reflexes, self.player.positioning, self.player.rebound_control, 
                    self.player.puck_handling]
        else:
            attrs = [self.player.skating, self.player.shooting, self.player.passing, 
                    self.player.defensive_awareness, self.player.hockey_iq]
        
        # Calculate standard deviation (lower = more versatile)
        avg = sum(attrs) / len(attrs)
        variance = sum((x - avg) ** 2 for x in attrs) / len(attrs)
        std_dev = variance ** 0.5
        
        # Convert to 1-10 scale (lower std_dev = higher versatility)
        return min(10.0, max(1.0, 10.0 - std_dev))

    def _calculate_consistency_index(self):
        """Calculate consistency based on determination and discipline."""
        consistency = (self.player.determination + self.player.discipline + 
                      getattr(self.player, 'composure', 50)) / 3
        return min(10.0, max(1.0, consistency / 10.0))

    def _calculate_development_potential(self):
        """Calculate development potential based on age and potential grade."""
        age = self.player.age
        potential_map = {'A': 9, 'B': 7, 'C': 5, 'D': 3, 'F': 1}
        base_potential = potential_map.get(getattr(self.player, 'potential_grade', 'C'), 5)
        
        # Adjust for age (younger = more potential)
        if age <= 20:
            age_factor = 1.2
        elif age <= 25:
            age_factor = 1.0
        elif age <= 30:
            age_factor = 0.7
        else:
            age_factor = 0.3
        
        return min(10.0, base_potential * age_factor)

    def _calculate_injury_risk(self):
        """Calculate injury risk factor."""
        injury_proneness = getattr(self.player, 'injury_proneness', 50)
        age = self.player.age
        
        # Higher injury proneness and age = higher risk
        base_risk = injury_proneness / 10.0
        
        if age >= 30:
            age_factor = 1.3
        elif age >= 25:
            age_factor = 1.0
        else:
            age_factor = 0.8
        
        return min(10.0, max(1.0, base_risk * age_factor))

    def _calculate_chemistry_impact(self):
        """Calculate team chemistry impact."""
        chemistry_attrs = [self.player.teamwork, self.player.leadership, 
                          getattr(self.player, 'discipline', 10)]
        avg_chemistry = sum(chemistry_attrs) / len(chemistry_attrs)
        return min(10.0, max(1.0, avg_chemistry / 2.0))

    def _draw_performance_profile(self, canvas):
        """Draw a simple performance profile visualization."""
        canvas.delete("all")
        
        # Define key attributes for the profile
        if self.player.primary_position == PlayerPosition.GOALIE:
            attrs = [
                ("Reflexes", self.player.reflexes),
                ("Positioning", self.player.positioning),
                ("Rebound", self.player.rebound_control),
                ("Mental", getattr(self.player, 'composure', 10))
            ]
        else:
            attrs = [
                ("Skating", self.player.skating),
                ("Shooting", self.player.shooting),
                ("Passing", self.player.passing),
                ("Defense", self.player.defensive_awareness),
                ("Mental", self.player.hockey_iq)
            ]
        
        # Draw horizontal bars for each attribute
        bar_height = 15
        max_width = 200
        start_y = 10
        
        for i, (name, value) in enumerate(attrs):
            y = start_y + (i * (bar_height + 5))
            
            # Background bar
            canvas.create_rectangle(60, y, 60 + max_width, y + bar_height, 
                                  fill=self.app.TITLE_BAR_COLOR, outline=self.app.TEXT_COLOR)
            
            # Value bar
            bar_width = int((value / 20.0) * max_width)
            bar_color = self._get_rating_color(value)
            canvas.create_rectangle(60, y, 60 + bar_width, y + bar_height, 
                                  fill=bar_color, outline=bar_color)
            
            # Label and value
            canvas.create_text(55, y + bar_height/2, text=name, anchor='e', 
                             fill=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 9))
            canvas.create_text(65 + max_width, y + bar_height/2, text=str(value), anchor='w',
                             fill=self.app.TEXT_COLOR, font=(self.app.FONT_FAMILY, 9, 'bold'))
                             
    def _create_simple_comparison(self, parent, row=4):
        """Creates a simple player comparison section."""
        comp_frame = self.app._create_panel(parent, "League Comparison", row, 0)
        
        # Create a structured layout for the comparison
        comp_grid = ttk.Frame(comp_frame, style='PlayerTab.TFrame')
        comp_grid.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        comp_frame.grid_columnconfigure(0, weight=1)
        comp_frame.grid_rowconfigure(0, weight=1)
        comp_grid.grid_columnconfigure(1, weight=1)
        
        overall = self.player.overall_rating()
        
        # Overall rating assessment
        if overall >= 17:
            rating_level = "Elite"
            rating_desc = "Top-tier league player"
        elif overall >= 15:
            rating_level = "Above Average"
            rating_desc = "Strong contributor"
        elif overall >= 13:
            rating_level = "Average"
            rating_desc = "Solid league player"
        else:
            rating_level = "Below Average"
            rating_desc = "Developing player"
            
        ttk.Label(comp_grid, text="League Level:", style='PlayerInfo.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(comp_grid, text=rating_level, style='PlayerValue.TLabel').grid(row=0, column=1, sticky='w', pady=2)
        
        # Age category
        if self.player.age <= 22:
            age_category = "Young Prospect"
        elif self.player.age <= 28:
            age_category = "Prime Years"
        else:
            age_category = "Veteran"
            
        ttk.Label(comp_grid, text="Age Category:", style='PlayerInfo.TLabel').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(comp_grid, text=age_category, style='PlayerValue.TLabel').grid(row=1, column=1, sticky='w', pady=2)
        
        # Position strength
        if self.player.primary_position.value == "Goalie":
            key_attr = self.player.goaltending
            skill_name = "Goaltending"
        else:
            shooting = getattr(self.player, 'shooting', 10)
            passing = getattr(self.player, 'passing', 10)
            skating = getattr(self.player, 'skating', 10)
            key_attr = max(shooting, passing, skating)
            if key_attr == shooting:
                skill_name = "Shooting"
            elif key_attr == passing:
                skill_name = "Passing"
            else:
                skill_name = "Skating"
            
        if key_attr >= 16:
            skill_level = "Elite"
        elif key_attr >= 14:
            skill_level = "Strong"
        elif key_attr >= 12:
            skill_level = "Average"
        else:
            skill_level = "Developing"
            
        ttk.Label(comp_grid, text="Best Skill:", style='PlayerInfo.TLabel').grid(row=2, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(comp_grid, text=f"{skill_name} ({skill_level})", style='PlayerValue.TLabel').grid(row=2, column=1, sticky='w', pady=2)
        
        # Overall assessment
        ttk.Label(comp_grid, text="Assessment:", style='PlayerInfo.TLabel').grid(row=3, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(comp_grid, text=rating_desc, style='PlayerValue.TLabel').grid(row=3, column=1, sticky='w', pady=2)
            
    def _create_league_standing(self, parent, row=5):
        """Creates a league standing and team context section."""
        standing_frame = self.app._create_panel(parent, "Team & League Context", row, 0)
        
        # Create a structured layout for the team context
        context_grid = ttk.Frame(standing_frame, style='PlayerTab.TFrame')
        context_grid.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        standing_frame.grid_columnconfigure(0, weight=1)
        standing_frame.grid_rowconfigure(0, weight=1)
        context_grid.grid_columnconfigure(1, weight=1)
        
        row_idx = 0
        
        # Current team
        ttk.Label(context_grid, text="Current Team:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(context_grid, text=self.player.team_name, style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
        row_idx += 1
        
        # League
        league_name = getattr(self.player, 'league', 'NHL')
        ttk.Label(context_grid, text="League:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(context_grid, text=league_name, style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
        row_idx += 1
        
        # Contract information
        if hasattr(self.player, 'contract') and self.player.contract:
            # Contract years
            years_remaining = getattr(self.player.contract, 'years_remaining', getattr(self.player.contract, 'years_left', 0))
            ttk.Label(context_grid, text="Contract Years:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(context_grid, text=f"{years_remaining} years", style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
            row_idx += 1
            
            # Salary
            salary = getattr(self.player.contract, 'salary', 0)
            ttk.Label(context_grid, text="Annual Salary:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(context_grid, text=f"${salary:,}", style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
            row_idx += 1
        else:
            ttk.Label(context_grid, text="Contract Status:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(context_grid, text="No active contract", style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
            row_idx += 1
            
        # Roster status
        if hasattr(self.player, 'roster_status'):
            ttk.Label(context_grid, text="Roster Status:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(context_grid, text=self.player.roster_status, style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
            row_idx += 1
        
        # Development potential
        if self.player.age < 25:
            ttk.Label(context_grid, text="Development:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
            ttk.Label(context_grid, text="Developing player", style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)
            row_idx += 1
        
        # Potential grade
        if hasattr(self.player, 'potential_grade'):
            potential = self.player.potential_grade
        else:
            potential = "Unknown"
        ttk.Label(context_grid, text="Potential:", style='PlayerInfo.TLabel').grid(row=row_idx, column=0, sticky='w', padx=(0, 10), pady=2)
        ttk.Label(context_grid, text=potential, style='PlayerValue.TLabel').grid(row=row_idx, column=1, sticky='w', pady=2)


class PlayerProfileWindow(InGamePopup):
    """Popup wrapper around PlayerProfileView (backward compatibility).

    New code should embed PlayerProfileView as a full-screen view via
    ``HockeyManagerGUI.show_screen('player_profile',
    f"Profile: {player.full_name}", PlayerProfileView, player)``
    instead of opening this card.
    """

    def __init__(self, parent, player, is_scouted=False, report=None):
        super().__init__(parent)
        self.title(f"Profile: {player.full_name}")
        # The profile view needs room: without an explicit size the card
        # opens at the default 560x420 popup size and the content renders
        # cramped/clipped. Match the modern card's footprint.
        try:
            self.geometry("980x760")
        except Exception:
            pass
        # Closing the card must tear down the popup card (manager-owned),
        # not just the inner frame.
        self._view = PlayerProfileView(self, player, is_scouted, report,
                                       app=parent)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
