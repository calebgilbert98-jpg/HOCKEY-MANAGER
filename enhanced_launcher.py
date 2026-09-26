"""
Puck Dynasty - Enhanced Professional Game Launcher
Comprehensive launcher with full NHL teams, advanced game setup, and background integration
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
from pathlib import Path
from datetime import datetime, date
import json
import random
import calendar
from PIL import Image, ImageTk

from modern_ui import AppColors, AppFonts, AppCard, AppButton, PillBadge


class _ThemedButton(tk.Button):
    """tk.Button with modern dark styling.

    Used where AppButton (canvas-based) can't drop in -- e.g. buttons
    whose enabled/disabled state is toggled via .configure(state=...).
    """
    def __init__(self, parent, style="primary", **kwargs):
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("cursor", "hand2")
        if style == "primary":
            kwargs.setdefault("bg", AppColors.ACCENT)
            kwargs.setdefault("fg", "#ffffff")
            kwargs.setdefault("activebackground", AppColors.ACCENT_DIM)
            kwargs.setdefault("activeforeground", "#ffffff")
            kwargs.setdefault("font", AppFonts.BODY_BOLD)
        elif style == "danger":
            kwargs.setdefault("bg", AppColors.DANGER)
            kwargs.setdefault("fg", "#ffffff")
            kwargs.setdefault("activebackground", "#d63a33")
            kwargs.setdefault("activeforeground", "#ffffff")
            kwargs.setdefault("font", AppFonts.BODY_BOLD)
        else:  # secondary
            kwargs.setdefault("bg", AppColors.BG_ELEVATED)
            kwargs.setdefault("fg", AppColors.TEXT_PRIMARY)
            kwargs.setdefault("activebackground", AppColors.BG_HOVER)
            kwargs.setdefault("activeforeground", AppColors.TEXT_PRIMARY)
            kwargs.setdefault("font", AppFonts.BODY)
        # Disabled-state colors (tkinter uses these automatically)
        kwargs.setdefault("disabledforeground", AppColors.TEXT_TERTIARY)
        super().__init__(parent, **kwargs)
        self._style = style

    def set_enabled(self, enabled):
        """Toggle enabled state with appropriate modern colors."""
        if enabled:
            bg = AppColors.ACCENT if self._style == "primary" else \
                 AppColors.DANGER if self._style == "danger" else AppColors.BG_ELEVATED
            self.configure(state="normal", bg=bg, fg="#ffffff" if self._style != "secondary" else AppColors.TEXT_PRIMARY)
        else:
            self.configure(state="disabled", bg=AppColors.BG_HOVER, fg=AppColors.TEXT_TERTIARY)


class SectionCard(tk.Frame):
    """Modern drop-in replacement for tk.LabelFrame.

    Renders as a charcoal card with a clean title label instead of the
    dated LabelFrame border. Children pack/grid into it directly, just
    like a LabelFrame.
    """
    def __init__(self, parent, text="", font=None, **kwargs):
        kwargs.pop("fg", None)  # LabelFrame text color -- not needed
        kwargs.setdefault("bg", AppColors.BG_ELEVATED)
        super().__init__(parent, **kwargs)
        title = text.strip()
        if title:
            tk.Label(self, text=title,
                     font=font or AppFonts.H2,
                     bg=AppColors.BG_ELEVATED,
                     fg=AppColors.TEXT_PRIMARY).pack(
                         anchor="w", padx=16, pady=(14, 6))
            # Subtle teal underline accent
            tk.Frame(self, bg=AppColors.ACCENT, height=2).pack(
                fill="x", padx=16, pady=(0, 10))


class EnhancedPuckDynastyLauncher(tk.Tk):
    """Enhanced professional game launcher with comprehensive options"""
    
    def __init__(self):
        print("Initializing Enhanced Puck Dynasty Launcher...")
        super().__init__()
        
        # All NHL teams organized by division
        self.nhl_teams = {
            # Eastern Conference
            "Metropolitan": {
                "Carolina Hurricanes": {"city": "Raleigh", "colors": ["#CC0000", "#000000"]},
                "Columbus Blue Jackets": {"city": "Columbus", "colors": ["#002654", "#CE1126"]},
                "New Jersey Devils": {"city": "Newark", "colors": ["#CE1126", "#000000"]},
                "New York Islanders": {"city": "New York", "colors": ["#00539B", "#F47D30"]},
                "New York Rangers": {"city": "New York", "colors": ["#0038A8", "#CE1126"]},
                "Philadelphia Flyers": {"city": "Philadelphia", "colors": ["#F74902", "#000000"]},
                "Pittsburgh Penguins": {"city": "Pittsburgh", "colors": ["#FCB514", "#000000"]},
                "Washington Capitals": {"city": "Washington", "colors": ["#041E42", "#C8102E"]}
            },
            "Atlantic": {
                "Boston Bruins": {"city": "Boston", "colors": ["#FFB81C", "#000000"]},
                "Buffalo Sabres": {"city": "Buffalo", "colors": ["#003087", "#FFB81C"]},
                "Detroit Red Wings": {"city": "Detroit", "colors": ["#CE1126", "#FFFFFF"]},
                "Florida Panthers": {"city": "Sunrise", "colors": ["#041E42", "#C8102E"]},
                "Montréal Canadiens": {"city": "Montreal", "colors": ["#AF1E2D", "#192168"]},
                "Ottawa Senators": {"city": "Ottawa", "colors": ["#C52032", "#000000"]},
                "Tampa Bay Lightning": {"city": "Tampa Bay", "colors": ["#002868", "#FFFFFF"]},
                "Toronto Maple Leafs": {"city": "Toronto", "colors": ["#003E7E", "#FFFFFF"]}
            },
            # Western Conference
            "Central": {
                "Chicago Blackhawks": {"city": "Chicago", "colors": ["#CF0A2C", "#000000"]},
                "Colorado Avalanche": {"city": "Denver", "colors": ["#6F263D", "#236192"]},
                "Dallas Stars": {"city": "Dallas", "colors": ["#006847", "#000000"]},
                "Minnesota Wild": {"city": "St. Paul", "colors": ["#154734", "#EAAA00"]},
                "Nashville Predators": {"city": "Nashville", "colors": ["#FFB81C", "#041E42"]},
                "St. Louis Blues": {"city": "St. Louis", "colors": ["#002F87", "#FCB514"]},
                "Utah Hockey Club": {"city": "Salt Lake City", "colors": ["#69BE28", "#000000"]},
                "Winnipeg Jets": {"city": "Winnipeg", "colors": ["#041E42", "#004C97"]}
            },
            "Pacific": {
                "Anaheim Ducks": {"city": "Anaheim", "colors": ["#F47A38", "#000000"]},
                "Calgary Flames": {"city": "Calgary", "colors": ["#C8102E", "#F1BE48"]},
                "Edmonton Oilers": {"city": "Edmonton", "colors": ["#041E42", "#FF4C00"]},
                "Los Angeles Kings": {"city": "Los Angeles", "colors": ["#111111", "#A2AAAD"]},
                "San Jose Sharks": {"city": "San Jose", "colors": ["#006D75", "#EA7200"]},
                "Seattle Kraken": {"city": "Seattle", "colors": ["#001628", "#99D9D9"]},
                "Vancouver Canucks": {"city": "Vancouver", "colors": ["#00205B", "#00843D"]},
                "Vegas Golden Knights": {"city": "Las Vegas", "colors": ["#B4975A", "#333F42"]}
            }
        }
        
        # State variables
        self.selected_save = None
        self.save_games = []
        self.selected_team = None
        self.background_image = None
        self.team_cards = {}
        # Setup-wizard config (set when the user completes the wizard; takes
        # precedence over the tab's own options in _start_main_game)
        self.wizard_config = None
        
        # Initialize default GM profile values
        self._initialize_random_gm_defaults()
        
        # Game setup variables
        self.setup_options = {
            'database_size': tk.StringVar(master=self, value="Small (8K players, 32 NHL+AHL teams)"),
            'start_date': tk.StringVar(master=self, value="October 1, 2024"),
            'season_length': tk.StringVar(master=self, value="Full Season (82 Games)"),
            'difficulty': tk.StringVar(master=self, value="Realistic"),
            'fantasy_draft': tk.BooleanVar(master=self, value=False),
            'salary_cap': tk.BooleanVar(master=self, value=True),
            'injuries': tk.BooleanVar(master=self, value=True),
            'morale_system': tk.BooleanVar(master=self, value=True),
            'realistic_progression': tk.BooleanVar(master=self, value=True),
            'trade_difficulty': tk.StringVar(master=self, value="Realistic"),
            'cpu_gm_intelligence': tk.StringVar(master=self, value="High"),
            'international_players': tk.BooleanVar(master=self, value=True)
        }
        
        # GM Profile variables - Initialize with random defaults
        self._initialize_random_gm_defaults()
        
        self.gm_profile = {
            'name': tk.StringVar(master=self, value=self.default_gm_name),
            'age': tk.StringVar(master=self, value=str(self.default_gm_age)),
            'experience': tk.StringVar(master=self, value=self.default_gm_experience),
            'background': tk.StringVar(master=self, value=self.default_gm_background),
            'management_style': tk.StringVar(master=self, value=self.default_gm_style),
            'reputation': tk.StringVar(master=self, value=self.default_gm_reputation),
            'contract_length': tk.StringVar(master=self, value=self.default_gm_contract)
        }
        
        # Add change callbacks to check readiness
        for var in self.gm_profile.values():
            var.trace('w', lambda *args: self.after_idle(self._check_readiness))
        
        # Add callbacks for setup options to trigger validation
        for var in self.setup_options.values():
            if isinstance(var, (tk.StringVar, tk.BooleanVar)):
                var.trace('w', lambda *args: self.after_idle(self._check_readiness))
        
        # Widget reference tracking system
        self.ui_widgets = {
            'game_setup': {},  # Will store Entry/Combobox widgets for game setup
            'gm_profile': {},  # Will store Entry/Combobox widgets for GM profile
            'team_selection': {}  # Will store Listbox/Treeview widgets for team selection
        }
        
        # Window configuration
        self.title("Puck Dynasty - Hockey Management Simulator")
        self.geometry("1400x900")
        self.minsize(1200, 750)
        self.configure(bg=AppColors.BG)
        
        # Initialize
        self._setup_window()
        self._load_background_image()
        self._create_interface()
        self._load_save_games()
        
        # Center window
        self._center_window()
        
        # Ensure proper window state and focus
        self.lift()  # Bring to front
        self.focus_set()  # Set focus
        
        # Set up window close protocol
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_window(self):
        """Configure window properties"""
        try:
            if os.path.exists("puck_dynasty_icon.ico"):
                self.iconbitmap("puck_dynasty_icon.ico")
        except:
            pass
        
        self.resizable(True, True)
        
    def _load_background_image(self):
        """Load and prepare background image"""
        try:
            # Try different possible filenames  
            possible_names = [
                "hockey manager background.png",
                "hockey_bg.png", 
                "background.png",
                "assets/hockey_bg.png"
            ]
            
            bg_path = None
            for name in possible_names:
                if os.path.exists(name):
                    bg_path = name
                    break
            
            if bg_path:
                # Load and process image
                original = Image.open(bg_path)
                
                # Get current screen size for better sizing
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                
                # Use larger base size for better quality
                window_size = (min(1400, screen_width), min(900, screen_height))
                original = original.resize(window_size, Image.Resampling.LANCZOS)
                
                # Apply dark overlay for better text readability
                overlay = Image.new('RGBA', original.size, (0, 0, 0, 140))
                if original.mode != 'RGBA':
                    original = original.convert('RGBA')
                
                # Composite the overlay
                self.background_image = Image.alpha_composite(original, overlay)
                
                print("Background image loaded successfully")
            else:
                print("Background image not found, using solid background")
                self.background_image = None
                
        except Exception as e:
            print(f"Could not load background image: {e}")
            self.background_image = None
            
    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
    def _create_interface(self):
        """Create the enhanced launcher interface"""
        # Create background with visible image integration
        if self.background_image is not None:
            try:
                # Create a main frame with the background
                self._create_background_interface()
            except Exception as e:
                print(f"Background image display failed ({e}), using regular interface")
                self._create_regular_interface()
        else:
            # Fallback to regular interface
            self._create_regular_interface()
    
    def _create_background_interface(self):
        """Create interface with visible background integration"""
        # Create main container frame
        main_container = tk.Frame(self, bg=AppColors.BG)
        main_container.pack(fill='both', expand=True)
        
        # Create header with background image section
        header_frame = tk.Frame(main_container, bg=AppColors.BG, height=120)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Background image display area in header
        bg_canvas = tk.Canvas(header_frame, height=120, highlightthickness=0, bg=AppColors.BG)
        bg_canvas.pack(fill='x', padx=20, pady=10)
        
        # Simple title without background image complications
        try:
            # Add title overlay without problematic background image
            overlay_frame = tk.Frame(header_frame, bg=AppColors.BG)
            overlay_frame.place(relx=0.5, rely=0.5, anchor='center')
            
            title_label = tk.Label(overlay_frame,
                                  text="PUCK DYNASTY",
                                  font=AppFonts.H1,
                                  bg=AppColors.BG, fg=AppColors.TEXT_PRIMARY)
            title_label.pack()
            
            subtitle_label = tk.Label(overlay_frame,
                                     text="Professional Hockey Management Simulator",
                                     font=AppFonts.SMALL,
                                     bg=AppColors.BG, fg=AppColors.TEXT_SECONDARY)
            subtitle_label.pack()
            
        except Exception as e:
            print(f"Header creation failed: {e}")
        
        # Create the rest of the interface normally
        self._create_main_interface(main_container)
    
    def _create_main_interface(self, parent):
        """Create the main tabbed interface"""
        # Status bar at top
        status_frame = tk.Frame(parent, bg=AppColors.BG_ELEVATED, height=30)
        status_frame.pack(fill='x')
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame,
                                   text="Ready to create your hockey dynasty...",
                                   font=AppFonts.CAPTION,
                                   bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY)
        self.status_label.pack(side='left', padx=20, pady=5)
        
        # Main content area with tabs (subtle hockey theme)
        content_frame = tk.Frame(parent, bg=AppColors.BG)  # Slightly lighter for contrast
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add subtle hockey-themed border
        border_frame = tk.Frame(content_frame, bg='#f85149', height=2)
        border_frame.pack(fill='x', pady=(0, 5))
        
        # Create notebook for tabs -- modern dark tab bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=AppColors.BG,
                        borderwidth=0, tabmargins=[8, 8, 8, 0])
        style.configure('TNotebook.Tab',
                        background=AppColors.BG_ELEVATED,
                        foreground=AppColors.TEXT_SECONDARY,
                        padding=[22, 10],
                        font=AppFonts.SMALL_BOLD,
                        borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', AppColors.BG_HOVER),
                              ('active', AppColors.BG_HOVER)],
                  foreground=[('selected', AppColors.TEXT_PRIMARY),
                              ('active', AppColors.TEXT_PRIMARY)])

        self.notebook = ttk.Notebook(content_frame, style='TNotebook')
        self.notebook.pack(fill='both', expand=True)

        # Create tabs - Team selection first for better workflow
        self._create_new_game_tab()      # Team Selection & Basic Options
        self._create_gm_profile_tab()    # GM Profile Creation
        self._create_advanced_setup_tab() # Advanced Configuration
        self._create_load_game_tab()     # Load Existing Games
        self._create_settings_tab()      # Launcher Settings

        # Bottom action bar with start button
        self._create_action_bar(parent)
        
        # Register widgets after all UI is created
        self.after_idle(self._register_widgets)
        
        # Initialize default values and force widget population
        self.after_idle(self._initialize_default_values)
        
        # Extra widget population step to ensure Comboboxes display values
        self.after(100, self._force_combobox_initialization)
        # Backup initialization in case of timing issues
        self.after(300, self._force_combobox_initialization)
                
    def _create_action_bar(self, parent):
        """Create bottom action bar with start button"""
        action_frame = tk.Frame(parent, bg=AppColors.BG_ELEVATED, height=80)
        action_frame.pack(fill='x', side='bottom')
        action_frame.pack_propagate(False)
        
        # Start game button
        self.start_button = tk.Button(action_frame,
                                     text="START GAME",
                                     font=AppFonts.H2,
                                     bg=AppColors.ACCENT, fg='white',
                                     relief='flat', bd=0,
                                     pady=15, padx=40,
                                     cursor='hand2',
                                     state='disabled',
                                     command=self._start_new_game)
        self.start_button.pack(side='right', padx=20, pady=20)
        
        # Import save button
        import_btn = tk.Button(action_frame,
                              text="Import Save",
                              font=AppFonts.SMALL,
                              bg=AppColors.ACCENT_DIM, fg='white',
                              relief='flat', bd=0,
                              pady=8, padx=15,
                              cursor='hand2',
                              command=self._import_save)
        import_btn.pack(side='left', padx=20, pady=25)
        
    def _create_regular_interface(self):
        """Create regular interface without background"""
        self.configure(bg=AppColors.BG)

        # Slim branded hero strip at the very top of the window
        try:
            from branding import SlimBanner
            SlimBanner(self, 'launcher_banner.png', height=130,
                       bg=AppColors.BG).pack(fill='x')
        except Exception:
            pass

        # Create a simple header without background
        header_frame = tk.Frame(self, bg=AppColors.BG_ELEVATED, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        title_row = tk.Frame(header_frame, bg=AppColors.BG_ELEVATED)
        title_row.pack(expand=True)

        try:
            from branding import load_logo
            self._launcher_logo = load_logo(self, size=48)
            if self._launcher_logo is not None:
                tk.Label(title_row, image=self._launcher_logo,
                         bg=AppColors.BG_ELEVATED).pack(side='left', padx=(0, 12))
        except Exception:
            pass

        title_label = tk.Label(title_row,
                              text="PUCK DYNASTY",
                              font=AppFonts.H1,
                              bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        title_label.pack(side='left')

        subtitle_label = tk.Label(header_frame,
                                 text="Professional Hockey Management Simulator",
                                 font=AppFonts.SMALL,
                                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY)
        subtitle_label.pack()

        # Create main interface
        self._create_main_interface(self)
        
    def _create_gm_profile_tab(self):
        """Create GM profile creation tab"""
        gm_frame = tk.Frame(self.notebook, bg=AppColors.BG_ELEVATED)
        self.notebook.add(gm_frame, text="Create GM")
        
        # Create scrollable frame
        canvas = tk.Canvas(gm_frame, bg=AppColors.BG_ELEVATED, highlightthickness=0)
        scrollbar = ttk.Scrollbar(gm_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=AppColors.BG_ELEVATED)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas width to scrollable frame width for horizontal expansion
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        canvas.bind('<Configure>', configure_scroll_region)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # GM Profile Header
        header_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
        header_frame.pack(fill='x', padx=15, pady=30)
        
        tk.Label(header_frame,
                text="Create Your General Manager Profile",
                font=AppFonts.H1,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).pack()
        
        tk.Label(header_frame,
                text="Define your identity as a hockey executive. Your choices will affect team morale, trade negotiations, and media relations.",
                font=AppFonts.SMALL,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                wraplength=800, justify='center').pack(pady=(10, 0))
        
        # Basic Info Section
        basic_frame = SectionCard(scrollable_frame, text="  Basic Information  ",
                                   font=AppFonts.H3,
                                   bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        basic_frame.pack(fill='x', padx=15, pady=20)
        
        basic_grid = tk.Frame(basic_frame, bg=AppColors.BG_ELEVATED)
        basic_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid weights for better space utilization
        basic_grid.grid_columnconfigure(0, weight=0)  # Label column
        basic_grid.grid_columnconfigure(1, weight=1)  # Entry/Combo column - expandable
        basic_grid.grid_columnconfigure(2, weight=0)  # Button column
        
        # Name
        tk.Label(basic_grid, text="Full Name:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=0, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.name_entry = tk.Entry(basic_grid, textvariable=self.gm_profile['name'],
                             font=AppFonts.SMALL)
        self.name_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10), pady=10)
        
        # Generate random name button
        tk.Button(basic_grid, text="Random",
                 font=AppFonts.CAPTION,
                 bg=AppColors.ACCENT_DIM, fg='white', relief='flat', bd=0,
                 pady=5, padx=10, cursor='hand2',
                 command=self._generate_random_gm_name).grid(row=0, column=2, pady=10)
        
        # Age
        tk.Label(basic_grid, text="Age:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=1, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.age_combo = ttk.Combobox(basic_grid, textvariable=self.gm_profile['age'],
                                values=[str(age) for age in range(28, 71)], 
                                state='readonly')
        self.age_combo.grid(row=1, column=1, sticky='ew', padx=(0, 10), pady=10)
        
        # Experience Level
        tk.Label(basic_grid, text="Experience:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=2, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.exp_combo = ttk.Combobox(basic_grid, textvariable=self.gm_profile['experience'],
                                values=["First-Time GM", "Assistant GM Experience", "Former GM", "Veteran Executive"], 
                                state='readonly')
        self.exp_combo.grid(row=2, column=1, sticky='ew', padx=(0, 10), pady=10)
        
        # Background Section
        background_frame = SectionCard(scrollable_frame, text="  Hockey Background  ",
                                        font=AppFonts.H3,
                                        bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        background_frame.pack(fill='x', padx=15, pady=20)
        
        bg_grid = tk.Frame(background_frame, bg=AppColors.BG_ELEVATED)
        bg_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid weights for better space utilization
        bg_grid.grid_columnconfigure(0, weight=0)  # Label column
        bg_grid.grid_columnconfigure(1, weight=1)  # Combo column - expandable
        
        # Background type
        tk.Label(bg_grid, text="Background:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=0, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.bg_combo = ttk.Combobox(bg_grid, textvariable=self.gm_profile['background'],
                               values=["Former Player", "Former Coach", "Former Scout", "Business Executive", "Analytics Expert"], 
                               state='readonly')
        self.bg_combo.grid(row=0, column=1, sticky='ew', pady=10)
        
        # Management Style
        tk.Label(bg_grid, text="Management Style:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=1, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.style_combo = ttk.Combobox(bg_grid, textvariable=self.gm_profile['management_style'],
                                  values=["Players' GM", "Strict Disciplinarian", "Analytics-Focused", "Balanced", "Old-School"], 
                                  state='readonly')
        self.style_combo.grid(row=1, column=1, sticky='ew', pady=10)
        
        # Contract Section
        contract_frame = SectionCard(scrollable_frame, text="  Contract Terms  ",
                                      font=AppFonts.H3,
                                      bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        contract_frame.pack(fill='x', padx=15, pady=20)
        
        contract_grid = tk.Frame(contract_frame, bg=AppColors.BG_ELEVATED)
        contract_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid weights for better space utilization
        contract_grid.grid_columnconfigure(0, weight=0)  # Label column
        contract_grid.grid_columnconfigure(1, weight=1)  # Combo column - expandable
        
        # Contract Length
        tk.Label(contract_grid, text="Contract Length:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=0, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.contract_combo = ttk.Combobox(contract_grid, textvariable=self.gm_profile['contract_length'],
                                     values=["1 Year (Prove It)", "2 Years", "3 Years", "4 Years", "5 Years (Long-term)"], 
                                     state='readonly')
        self.contract_combo.grid(row=0, column=1, sticky='ew', pady=10)
        
        # Starting Reputation
        tk.Label(contract_grid, text="Initial Reputation:", font=AppFonts.SMALL_BOLD,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).grid(row=1, column=0, sticky='w', pady=10, padx=(0, 15))
        
        self.rep_combo = ttk.Combobox(contract_grid, textvariable=self.gm_profile['reputation'],
                                values=["Unknown", "Rising Star", "Proven Executive", "Legendary"], 
                                state='readonly')
        self.rep_combo.grid(row=1, column=1, sticky='ew', pady=10)
        
        # Profile Preview
        preview_frame = SectionCard(scrollable_frame, text="  Profile Preview  ",
                                     font=AppFonts.H3,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        preview_frame.pack(fill='x', padx=15, pady=20)
        
        self.gm_preview_text = tk.Text(preview_frame, height=6, width=70,
                                      font=AppFonts.SMALL,
                                      bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                                      relief='flat', bd=0, wrap='word')
        self.gm_preview_text.pack(padx=20, pady=20)
        
        # Update preview when values change
        for var in self.gm_profile.values():
            var.trace_add('write', lambda *args: self._update_gm_preview())
        
        # Generate profile button
        generate_btn = tk.Button(scrollable_frame,
                               text="Generate Random Profile",
                               font=AppFonts.BODY_BOLD,
                               bg=AppColors.ACCENT_DIM, fg='white',
                               relief='flat', bd=0, pady=10, padx=20,
                               cursor='hand2',
                               command=self._generate_random_gm_profile)
        generate_btn.pack(pady=20)
        
        # Initial preview update
        self._update_gm_preview()
        
    def _generate_random_gm_name(self):
        """Generate a random GM name"""
        first_names = ["Alex", "Jordan", "Casey", "Taylor", "Morgan", "Jamie", "Riley", "Cameron", "Blake", "Avery",
                      "Michael", "David", "John", "Robert", "Chris", "Daniel", "Mark", "Paul", "Steve", "Kevin"]
        last_names = ["Anderson", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                     "Hernandez", "Lopez", "Gonzalez", "Wilson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee"]
        
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        self.gm_profile['name'].set(name)
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Random GM name generated: {name}")
        self._check_readiness()
        
    def _generate_random_gm_profile(self):
        """Generate a complete random GM profile"""
        self._generate_random_gm_name()
        self.gm_profile['age'].set(str(random.randint(30, 65)))
        self.gm_profile['experience'].set(random.choice(["First-Time GM", "Assistant GM Experience", "Former GM", "Veteran Executive"]))
        self.gm_profile['background'].set(random.choice(["Former Player", "Former Coach", "Former Scout", "Business Executive", "Analytics Expert"]))
        self.gm_profile['management_style'].set(random.choice(["Players' GM", "Strict Disciplinarian", "Analytics-Focused", "Balanced", "Old-School"]))
        self.gm_profile['contract_length'].set(random.choice(["2 Years", "3 Years", "4 Years"]))
        self.gm_profile['reputation'].set(random.choice(["Unknown", "Rising Star"]))
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Complete GM profile generated: {self.gm_profile['name'].get()}")
        
        # Force widgets to display the new random values
        print("Refreshing widgets with new random GM profile...")
        self._force_initial_widget_display()
        self._force_combobox_initialization()
        
        # Force update the preview
        self._update_gm_preview()
        self._check_readiness()
        
    def _force_ui_refresh(self):
        """Force all UI widgets to refresh and show updated StringVar values"""
        try:
            # Force immediate update of all pending UI changes
            self.update_idletasks()
            
            # Trigger widget refresh by accessing all StringVar values
            # This forces tkinter to refresh the display
            for var in self.setup_options.values():
                if hasattr(var, 'get'):
                    var.get()  # Access forces refresh
                    
            for var in self.gm_profile.values():
                if hasattr(var, 'get'):
                    var.get()  # Access forces refresh
            
            # Force notebook tab refresh if it exists
            if hasattr(self, 'notebook'):
                current_tab = self.notebook.select()
                if current_tab:
                    self.notebook.select(current_tab)  # Refresh current tab
            
            # Force main window update
            self.update()
            
            # Force Combobox widgets to display their StringVar values
            self._force_initial_widget_display()
            self._force_combobox_initialization()
            
            # Additional refresh after a brief delay
            self.after_idle(lambda: self.update_idletasks())
            
        except Exception as e:
            print(f"UI refresh error: {e}")

    def _update_gm_preview(self):
        """Update the GM profile preview"""
        if not hasattr(self, 'gm_preview_text'):
            return
            
        name = self.gm_profile['name'].get() or "General Manager"
        age = self.gm_profile['age'].get()
        experience = self.gm_profile['experience'].get()
        background = self.gm_profile['background'].get()
        style = self.gm_profile['management_style'].get()
        contract = self.gm_profile['contract_length'].get()
        reputation = self.gm_profile['reputation'].get()
        
        preview_text = f"""GM Profile: {name} (Age {age})

Background: {background} with {experience.lower()} level experience
Management Style: {style}
Contract: {contract}
League Reputation: {reputation}

This profile will influence player relationships, media interactions, and trade negotiations throughout your career. Your background and style will determine how players and other GMs perceive you."""
        
        self.gm_preview_text.delete(1.0, tk.END)
        self.gm_preview_text.insert(1.0, preview_text)
        
    def _create_new_game_tab(self):
        """Create comprehensive new game setup tab"""
        new_game_frame = tk.Frame(self.notebook, bg=AppColors.BG_ELEVATED)
        self.notebook.add(new_game_frame, text="Choose Team")
        
        # Create scrollable frame for new game content
        canvas = tk.Canvas(new_game_frame, bg=AppColors.BG_ELEVATED, highlightthickness=0)
        scrollbar = ttk.Scrollbar(new_game_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=AppColors.BG_ELEVATED)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas width to scrollable frame width for horizontal expansion
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        canvas.bind('<Configure>', configure_scroll_region)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Team Selection Section
        self._create_team_selection(scrollable_frame)
        
        # Game Options Section
        self._create_game_options(scrollable_frame)
        
        # Setup wizard shortcut (Quick Start / Custom Setup with league
        # selection, fog of war, per-league sim detail)
        wiz_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
        wiz_frame.pack(fill='x', pady=(0, 10))
        tk.Button(wiz_frame,
                  text="Open Setup Wizard",
                  font=AppFonts.BODY_BOLD,
                  bg=AppColors.ACCENT, fg=AppColors.TEXT_PRIMARY,
                  relief='flat', bd=0, pady=10, padx=40,
                  cursor='hand2',
                  command=self._open_setup_wizard).pack()

        # Ready to Start Check
        ready_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
        ready_frame.pack(fill='x', pady=20)
        
        self.ready_status_label = tk.Label(ready_frame,
                                          text="Complete GM Profile and select team to start",
                                          font=AppFonts.BODY_BOLD,
                                          bg=AppColors.BG_ELEVATED, fg=AppColors.WARNING)
        self.ready_status_label.pack()
        
        # Start Game Button
        start_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
        start_frame.pack(fill='x', pady=20)
        
        self.start_btn = tk.Button(start_frame,
                                  text="START NEW GAME",
                                  font=AppFonts.H2,
                                  bg=AppColors.BG_HOVER, fg=AppColors.TEXT_SECONDARY,
                                  relief='flat', bd=0, pady=15, padx=60,
                                  cursor='hand2', state='disabled',
                                  command=self._start_new_game)
        self.start_btn.pack()
        
        # Check readiness initially
        self._check_game_readiness()
        
    def _create_advanced_setup_tab(self):
        """Create advanced game setup options tab"""
        advanced_frame = tk.Frame(self.notebook, bg=AppColors.BG_ELEVATED)
        self.notebook.add(advanced_frame, text="Advanced Setup")
        
        # Create scrollable frame
        canvas = tk.Canvas(advanced_frame, bg=AppColors.BG_ELEVATED, highlightthickness=0)
        scrollbar = ttk.Scrollbar(advanced_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=AppColors.BG_ELEVATED)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas width to scrollable frame width for horizontal expansion
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        canvas.bind('<Configure>', configure_scroll_region)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Advanced Setup Header
        header_frame = tk.Frame(scrollable_frame, bg=AppColors.BG_ELEVATED)
        header_frame.pack(fill='x', padx=15, pady=30)
        
        tk.Label(header_frame,
                text="Advanced Game Configuration",
                font=AppFonts.H1,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY).pack()
        
        tk.Label(header_frame,
                text="Fine-tune your hockey management experience with comprehensive gameplay options.",
                font=AppFonts.SMALL,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                wraplength=800, justify='center').pack(pady=(10, 0))
        
        # League & Database Options
        league_frame = SectionCard(scrollable_frame, text="  League & Database Options  ",
                                    font=AppFonts.H3,
                                    bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        league_frame.pack(fill='x', padx=15, pady=20)
        
        league_grid = tk.Frame(league_frame, bg=AppColors.BG_ELEVATED)
        league_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid to expand horizontally
        league_grid.grid_columnconfigure(0, weight=0)  # Label column
        league_grid.grid_columnconfigure(1, weight=1)  # Control column - expandable
        league_grid.grid_columnconfigure(2, weight=2)  # Tooltip column - more expandable
        
        self._create_advanced_option_row(league_grid, 0, "Database Size:",
                                       self.setup_options['database_size'],
                                       ["Small (8K players, 32 NHL+AHL teams)", 
                                        "Medium (25K players, 5 leagues)", 
                                        "Large (50K players, 12 leagues)", 
                                        "Massive (100K players, 25 leagues)"],
                                       "Determines the number of teams, players, and depth of the hockey world")
        
        self._create_advanced_option_row(league_grid, 1, "International Players:",
                                       self.setup_options['international_players'],
                                       [True, False], 
                                       "Include players from European leagues, juniors, and international prospects",
                                       is_checkbox=True)
        
        # Season Configuration  
        season_frame = SectionCard(scrollable_frame, text="  Season Configuration  ",
                                    font=AppFonts.H3,
                                    bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        season_frame.pack(fill='x', padx=15, pady=20)
        
        season_grid = tk.Frame(season_frame, bg=AppColors.BG_ELEVATED)
        season_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid to expand horizontally
        season_grid.grid_columnconfigure(0, weight=0)  # Label column
        season_grid.grid_columnconfigure(1, weight=1)  # Control column - expandable
        season_grid.grid_columnconfigure(2, weight=2)  # Tooltip column - more expandable
        
        self._create_advanced_option_row(season_grid, 0, "Season Start Date:",
                                       self.setup_options['start_date'],
                                       ["August 1, 2024 (Long Training Camp)", "September 1, 2024 (Extended Preseason)", 
                                        "October 1, 2024 (Regular Start)", "November 1, 2024 (Mid-Season Start)"],
                                       "Earlier start = longer training camp, more player development time")
        
        self._create_advanced_option_row(season_grid, 1, "Season Length:",
                                       self.setup_options['season_length'],
                                       ["Short Season (20 Games)", "Half Season (41 Games)", 
                                        "Full Season (82 Games)", "Extended Season (100+ Games)"],
                                       "Number of regular season games per team")
        
        # Realism & Difficulty
        realism_frame = SectionCard(scrollable_frame, text="  Realism & Difficulty  ",
                                     font=AppFonts.H3,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        realism_frame.pack(fill='x', padx=15, pady=20)
        
        realism_grid = tk.Frame(realism_frame, bg=AppColors.BG_ELEVATED)
        realism_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid to expand horizontally
        realism_grid.grid_columnconfigure(0, weight=0)  # Label column
        realism_grid.grid_columnconfigure(1, weight=1)  # Control column - expandable
        realism_grid.grid_columnconfigure(2, weight=2)  # Tooltip column - more expandable
        
        self._create_advanced_option_row(realism_grid, 0, "Overall Difficulty:",
                                       self.setup_options['difficulty'],
                                       ["Rookie (Easy)", "Amateur (Moderate)", "Professional (Challenging)", 
                                        "Realistic (Hard)", "Hall of Fame (Expert)"],
                                       "Affects AI intelligence, trade difficulty, and player development rates")
        
        self._create_advanced_option_row(realism_grid, 1, "Trade Difficulty:",
                                       self.setup_options['trade_difficulty'],
                                       ["Very Easy", "Easy", "Realistic", "Hard", "Nearly Impossible"],
                                       "How difficult it is to complete trades with CPU teams")
        
        self._create_advanced_option_row(realism_grid, 2, "CPU GM Intelligence:",
                                       self.setup_options['cpu_gm_intelligence'],
                                       ["Low (Predictable)", "Medium (Balanced)", "High (Challenging)", "Maximum (Ruthless)"],
                                       "How smart and aggressive CPU general managers are")
        
        # Gameplay Features
        gameplay_frame = SectionCard(scrollable_frame, text="  Gameplay Features  ",
                                      font=AppFonts.H3,
                                      bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        gameplay_frame.pack(fill='x', padx=15, pady=20)
        
        gameplay_grid = tk.Frame(gameplay_frame, bg=AppColors.BG_ELEVATED)
        gameplay_grid.pack(fill='x', padx=15, pady=15)
        
        # Configure grid columns to expand horizontally
        gameplay_grid.grid_columnconfigure(0, weight=1)  # Left column
        gameplay_grid.grid_columnconfigure(1, weight=1)  # Right column
        
        # Row 0
        self._create_advanced_checkbox_option(gameplay_grid, 0, 0, "Fantasy Draft", 
                                            self.setup_options['fantasy_draft'],
                                            "Redistribute all players among teams before season start")
        
        self._create_advanced_checkbox_option(gameplay_grid, 0, 1, "Salary Cap", 
                                            self.setup_options['salary_cap'],
                                            "Enable realistic salary cap management ($83.5M limit)")
        
        # Row 1
        self._create_advanced_checkbox_option(gameplay_grid, 1, 0, "Injuries & Fatigue", 
                                            self.setup_options['injuries'],
                                            "Enable player injuries, recovery system, and fatigue management")
        
        self._create_advanced_checkbox_option(gameplay_grid, 1, 1, "Morale & Chemistry", 
                                            self.setup_options['morale_system'],
                                            "Enable player morale, team chemistry, and locker room dynamics")
        
        # Row 2
        self._create_advanced_checkbox_option(gameplay_grid, 2, 0, "Realistic Progression", 
                                            self.setup_options['realistic_progression'],
                                            "Players develop and decline based on realistic age curves and usage")
        
        # Preset configurations
        presets_frame = SectionCard(scrollable_frame, text="  Configuration Presets  ",
                                     font=AppFonts.H3,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        presets_frame.pack(fill='x', padx=15, pady=20)
        
        presets_grid = tk.Frame(presets_frame, bg=AppColors.BG_ELEVATED)
        presets_grid.pack(fill='x', padx=20, pady=20)
        
        preset_buttons = [
            ("Arcade Mode", self._apply_arcade_preset, "Fast-paced, simplified gameplay"),
            ("Realistic NHL", self._apply_realistic_preset, "Authentic NHL experience"),
            ("Challenge Mode", self._apply_challenge_preset, "Maximum difficulty and realism"),
            ("Quick Season", self._apply_quick_preset, "Short season for faster gameplay")
        ]
        
        for i, (text, command, tooltip) in enumerate(preset_buttons):
            row, col = i // 2, i % 2
            
            btn_frame = tk.Frame(presets_grid, bg=AppColors.BG_ELEVATED)
            btn_frame.grid(row=row, column=col, padx=10, pady=10, sticky='ew')
            
            btn = tk.Button(btn_frame, text=text,
                           font=AppFonts.LABEL,
                           bg=AppColors.ACCENT_DIM, fg='white',
                           relief='flat', bd=0, pady=8, padx=15,
                           cursor='hand2', command=command)
            btn.pack()
            
            tk.Label(btn_frame, text=tooltip,
                    font=AppFonts.CAPTION,
                    bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY).pack(pady=(5, 0))
            
        presets_grid.grid_columnconfigure(0, weight=1)
        presets_grid.grid_columnconfigure(1, weight=1)
        
    def _create_advanced_option_row(self, parent, row, label_text, var, values, tooltip, is_checkbox=False):
        """Create an advanced option row with enhanced styling"""
        # Configure grid weights for better space utilization
        parent.grid_columnconfigure(0, weight=0)  # Label column - fixed width
        parent.grid_columnconfigure(1, weight=1)  # Control column - expandable
        parent.grid_columnconfigure(2, weight=2)  # Tooltip column - more expandable
        
        # Label
        label = tk.Label(parent, text=label_text,
                        font=AppFonts.SMALL_BOLD,
                        bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        label.grid(row=row, column=0, sticky='w', padx=(0, 15), pady=12)
        
        if is_checkbox:
            # Checkbox
            checkbox = tk.Checkbutton(parent, variable=var,
                                     font=AppFonts.SMALL,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                                     selectcolor='#2A2A2A',
                                     activebackground='#2A2A2A')
            checkbox.grid(row=row, column=1, sticky='w', pady=12)
        else:
            # Combobox - expand to fill available space
            combo = ttk.Combobox(parent, textvariable=var,
                               values=values, state='readonly',
                               font=AppFonts.SMALL)
            combo.grid(row=row, column=1, sticky='ew', padx=(0, 15), pady=12)
        
        # Tooltip - expand to fill available space
        tooltip_label = tk.Label(parent, text=tooltip,
                               font=AppFonts.CAPTION,
                               bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                               wraplength=400, justify='left')
        tooltip_label.grid(row=row, column=2, sticky='ew', padx=(0, 5), pady=12)
        
    def _create_advanced_checkbox_option(self, parent, row, col, text, var, tooltip):
        """Create an advanced checkbox option with enhanced layout"""
        frame = tk.Frame(parent, bg=AppColors.BG_ELEVATED, relief='solid', bd=1)
        frame.grid(row=row, column=col, sticky='ew', padx=5, pady=8)
        
        parent.grid_columnconfigure(col, weight=1)
        
        checkbox = tk.Checkbutton(frame, text=text, variable=var,
                                 font=AppFonts.LABEL,
                                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                                 selectcolor='#3A3A3A',
                                 activebackground='#2A2A2A')
        checkbox.pack(anchor='w', padx=12, pady=(12, 5))
        
        tooltip_label = tk.Label(frame, text=tooltip,
                               font=AppFonts.CAPTION,
                               bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                               wraplength=300, justify='left')
        tooltip_label.pack(anchor='w', padx=12, pady=(0, 12))
        
    # Preset configuration methods
    def _apply_arcade_preset(self):
        """Apply arcade mode preset"""
        # Game settings
        self.setup_options['database_size'].set("Small (8K players, 32 NHL+AHL teams)")
        self.setup_options['season_length'].set("Short Season (20 Games)")
        self.setup_options['difficulty'].set("Amateur (Moderate)")
        self.setup_options['trade_difficulty'].set("Easy")
        self.setup_options['cpu_gm_intelligence'].set("Medium (Balanced)")
        self.setup_options['fantasy_draft'].set(True)
        self.setup_options['salary_cap'].set(False)
        self.setup_options['injuries'].set(False)
        self.setup_options['realistic_progression'].set(False)
        
        # GM Profile - Generate a casual arcade-style GM
        arcade_names = ["Flash Gordon", "Speed Racer", "Rocket Johnson", "Turbo Smith", "Blaze Williams"]
        self.gm_profile['name'].set(random.choice(arcade_names))
        self.gm_profile['age'].set(str(random.randint(28, 40)))
        self.gm_profile['experience'].set("First-Time GM")
        self.gm_profile['background'].set("Former Player")
        self.gm_profile['management_style'].set("Players' GM")
        self.gm_profile['contract_length'].set("3 Years")
        self.gm_profile['reputation'].set("Rising Star")
        
        # Team selection - Pick an exciting arcade-friendly team
        arcade_teams = [
            ("Toronto Maple Leafs", "Toronto"),
            ("Edmonton Oilers", "Edmonton"), 
            ("Colorado Avalanche", "Denver"),
            ("Tampa Bay Lightning", "Tampa Bay")
        ]
        team_name, city = random.choice(arcade_teams)
        self._select_team(team_name, city)
        
        # COMPREHENSIVE UI REFRESH with all techniques
        print("Applying Arcade preset with enhanced refresh...")
        
        # CRITICAL: Force StringVars to trigger widget updates
        self._force_stringvar_refresh()
        self._force_ui_refresh()
        self._force_widget_updates()  # Direct widget update method
        
        # Schedule additional refresh to ensure all updates are visible
        self.after(100, self._final_refresh_pass)
        
        # Force immediate visual update by switching notebook tabs
        self._cycle_notebook_tabs()
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Arcade Mode preset applied - Fast, simplified gameplay")
        self._update_gm_preview()
        
        print("Arcade preset applied with enhanced refresh")
        
        # Schedule another UI refresh after a brief moment to ensure all widgets update
        self.after(50, self._force_ui_refresh)
        
        self._check_readiness()
        
    def _apply_realistic_preset(self):
        """Apply realistic NHL preset"""
        # Game settings
        self.setup_options['database_size'].set("Large (50K players, 12 leagues)")
        self.setup_options['season_length'].set("Full Season (82 Games)")
        self.setup_options['difficulty'].set("Realistic (Hard)")
        self.setup_options['trade_difficulty'].set("Realistic")
        self.setup_options['cpu_gm_intelligence'].set("High (Challenging)")
        self.setup_options['fantasy_draft'].set(False)
        self.setup_options['salary_cap'].set(True)
        self.setup_options['injuries'].set(True)
        self.setup_options['realistic_progression'].set(True)
        
        # GM Profile - Generate a realistic professional GM
        realistic_names = ["David Thompson", "Michael Roberts", "James Wilson", "Robert Anderson", "William Clarke"]
        self.gm_profile['name'].set(random.choice(realistic_names))
        self.gm_profile['age'].set(str(random.randint(35, 55)))
        self.gm_profile['experience'].set(random.choice(["Assistant GM Experience", "Former GM"]))
        self.gm_profile['background'].set(random.choice(["Former Coach", "Former Scout", "Business Executive"]))
        self.gm_profile['management_style'].set("Analytics-Focused")
        self.gm_profile['contract_length'].set("4 Years")
        self.gm_profile['reputation'].set("Unknown")
        
        # Team selection - Pick a realistic challenge team
        realistic_teams = [
            ("Chicago Blackhawks", "Chicago"),
            ("San Jose Sharks", "San Jose"),
            ("Ottawa Senators", "Ottawa"),
            ("Buffalo Sabres", "Buffalo")
        ]
        team_name, city = random.choice(realistic_teams)
        self._select_team(team_name, city)
        
        # COMPREHENSIVE UI REFRESH with all techniques
        print("Applying Realistic preset with enhanced refresh...")
        
        # CRITICAL: Force StringVars to trigger widget updates
        self._force_stringvar_refresh()
        self._force_ui_refresh()
        self._force_widget_updates()  # Direct widget update method
        
        # Schedule additional refresh to ensure all updates are visible
        self.after(100, self._final_refresh_pass)
        
        # Force immediate visual update by switching notebook tabs
        self._cycle_notebook_tabs()
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Realistic NHL preset applied - Authentic experience with full features")
        self._update_gm_preview()
        
        print("Realistic preset applied with enhanced refresh")
        
        # Schedule another UI refresh after a brief moment to ensure all widgets update
        self.after(50, self._force_ui_refresh)
        
        self._check_readiness()
        
    def _apply_challenge_preset(self):
        """Apply challenge mode preset"""
        # Game settings
        self.setup_options['database_size'].set("Massive (100K players, 25 leagues)")
        self.setup_options['season_length'].set("Full Season (82 Games)")
        self.setup_options['difficulty'].set("Hall of Fame (Expert)")
        self.setup_options['trade_difficulty'].set("Nearly Impossible")
        self.setup_options['cpu_gm_intelligence'].set("Maximum (Ruthless)")
        self.setup_options['fantasy_draft'].set(False)
        self.setup_options['salary_cap'].set(True)
        self.setup_options['injuries'].set(True)
        self.setup_options['realistic_progression'].set(True)
        
        # GM Profile - Generate an experienced challenge-ready GM
        challenge_names = ["Alex Thornton", "Morgan Steele", "Cameron Cross", "Jordan Blake", "Riley Stone"]
        self.gm_profile['name'].set(random.choice(challenge_names))
        self.gm_profile['age'].set(str(random.randint(45, 65)))
        self.gm_profile['experience'].set("Veteran Executive")
        self.gm_profile['background'].set(random.choice(["Former GM", "Former Coach"]))
        self.gm_profile['management_style'].set("Strict Disciplinarian")
        self.gm_profile['contract_length'].set("2 Years")
        self.gm_profile['reputation'].set("Unknown")
        
        # Team selection - Pick the most challenging rebuild teams
        challenge_teams = [
            ("Arizona Coyotes", "Tempe"),
            ("Anaheim Ducks", "Anaheim"),
            ("Columbus Blue Jackets", "Columbus"),
            ("Montreal Canadiens", "Montreal")
        ]
        team_name, city = random.choice(challenge_teams)
        self._select_team(team_name, city)
        
        # COMPREHENSIVE UI REFRESH with all techniques
        print("Applying Challenge preset with enhanced refresh...")
        
        # CRITICAL: Force StringVars to trigger widget updates
        self._force_stringvar_refresh()
        self._force_ui_refresh()
        self._force_widget_updates()  # Direct widget update method
        
        # Schedule additional refresh to ensure all updates are visible
        self.after(100, self._final_refresh_pass)
        
        # Force immediate visual update by switching notebook tabs
        self._cycle_notebook_tabs()
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Challenge Mode preset applied - Maximum difficulty and realism")
        self._update_gm_preview()
        
        print("Challenge preset applied with enhanced refresh")
        
        # Schedule another UI refresh after a brief moment to ensure all widgets update
        self.after(50, self._force_ui_refresh)
        
        self._check_readiness()
        
    def _apply_quick_preset(self):
        """Apply quick season preset"""
        # Game settings
        self.setup_options['database_size'].set("Small (8K players, 32 NHL+AHL teams)")
        self.setup_options['season_length'].set("Half Season (41 Games)")
        self.setup_options['difficulty'].set("Professional (Challenging)")
        self.setup_options['trade_difficulty'].set("Realistic")
        self.setup_options['cpu_gm_intelligence'].set("High (Challenging)")
        self.setup_options['fantasy_draft'].set(False)
        self.setup_options['salary_cap'].set(True)
        self.setup_options['injuries'].set(True)
        self.setup_options['realistic_progression'].set(True)
        
        # GM Profile - Generate a quick-start ready GM
        quick_names = ["Sam Parker", "Taylor Mitchell", "Casey Brooks", "Drew Collins", "Quinn Murphy"]
        self.gm_profile['name'].set(random.choice(quick_names))
        self.gm_profile['age'].set(str(random.randint(30, 50)))
        self.gm_profile['experience'].set(random.choice(["First-Time GM", "Assistant GM Experience"]))
        self.gm_profile['background'].set(random.choice(["Former Player", "Analytics Expert"]))
        self.gm_profile['management_style'].set("Balanced")
        self.gm_profile['contract_length'].set("3 Years")
        self.gm_profile['reputation'].set("Rising Star")
        
        # Team selection - Pick balanced, competitive teams for quick play
        quick_teams = [
            ("Nashville Predators", "Nashville"),
            ("Dallas Stars", "Dallas"),
            ("Seattle Kraken", "Seattle"),
            ("Vegas Golden Knights", "Las Vegas")
        ]
        team_name, city = random.choice(quick_teams)
        self._select_team(team_name, city)
        
        # COMPREHENSIVE UI REFRESH with all techniques
        print("Applying Quick preset with enhanced refresh...")
        
        # CRITICAL: Force StringVars to trigger widget updates
        self._force_stringvar_refresh()
        self._force_ui_refresh()
        self._force_widget_updates()  # Direct widget update method
        
        # Schedule additional refresh to ensure all updates are visible
        self.after(100, self._final_refresh_pass)
        
        # Force immediate visual update by switching notebook tabs
        self._cycle_notebook_tabs()
        
        # Update status and trigger validation
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Quick Season preset applied - Shorter season for faster gameplay")
        self._update_gm_preview()
        
        print("Quick preset applied with enhanced refresh")
        
        # Schedule another UI refresh after a brief moment to ensure all widgets update
        self.after(50, self._force_ui_refresh)
        
        self._check_readiness()
        
    def _check_game_readiness(self):
        """Check if all requirements are met to start the game - uses unified validation"""
        # Use the comprehensive validation system (only run once, callbacks handle updates)
        self._check_readiness()
        
    def _create_team_selection(self, parent):
        """Create comprehensive NHL team selection"""
        team_frame = SectionCard(parent, text="  Choose Your Team  ",
                                  font=AppFonts.H2,
                                  bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        team_frame.pack(fill='x', padx=20, pady=20)
        
        # Team selection info
        info_label = tk.Label(team_frame,
                             text="Select from all 32 NHL teams. Click a team card to select your franchise.",
                             font=AppFonts.SMALL,
                             bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY)
        info_label.pack(pady=(10, 5))
        
        # Random team button
        random_frame = tk.Frame(team_frame, bg=AppColors.BG_ELEVATED)
        random_frame.pack(pady=10)
        
        random_btn = tk.Button(random_frame,
                              text="Random Team",
                              font=AppFonts.SMALL_BOLD,
                              bg=AppColors.ACCENT_DIM, fg='white',
                              relief='flat', bd=0, pady=8, padx=20,
                              cursor='hand2',
                              command=self._select_random_team)
        random_btn.pack()
        
        # Selected team display
        self.selected_team_frame = tk.Frame(team_frame, bg=AppColors.BG_ELEVATED, relief='solid', bd=2)
        self.selected_team_frame.pack(fill='x', padx=20, pady=10)
        
        self.selected_team_label = tk.Label(self.selected_team_frame,
                                           text="No team selected",
                                           font=AppFonts.H3,
                                           bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        self.selected_team_label.pack(pady=15)
        
        # Create team grid by conference and division
        self._create_team_grid(team_frame)
        
    def _create_team_grid(self, parent):
        """Create organized team selection grid"""
        grid_container = tk.Frame(parent, bg=AppColors.BG_ELEVATED)
        grid_container.pack(fill='both', expand=True, padx=5, pady=10)
        
        # Eastern Conference
        east_frame = SectionCard(grid_container, text="  Eastern Conference  ",
                                  font=AppFonts.BODY_BOLD,
                                  bg=AppColors.BG_ELEVATED, fg=AppColors.INFO)
        east_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Western Conference
        west_frame = SectionCard(grid_container, text="  Western Conference  ",
                                  font=AppFonts.BODY_BOLD,
                                  bg=AppColors.BG_ELEVATED, fg='#FF6B6B')
        west_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Create division frames
        divisions = {
            'Metropolitan': east_frame,
            'Atlantic': east_frame,
            'Central': west_frame,
            'Pacific': west_frame
        }
        
        for division, teams in self.nhl_teams.items():
            div_frame = SectionCard(divisions[division], text=f"  {division} Division  ",
                                     font=AppFonts.LABEL,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY)
            div_frame.pack(fill='x', padx=3, pady=3)
            
            # Create team buttons in a grid (2 columns)
            team_grid = tk.Frame(div_frame, bg=AppColors.BG_ELEVATED)
            team_grid.pack(fill='x', padx=3, pady=3)
            
            team_list = list(teams.keys())
            for i, team_name in enumerate(team_list):
                team_info = teams[team_name]
                
                row = i // 2
                col = i % 2
                
                # Create team button with colors
                team_btn = tk.Button(team_grid,
                                   text=team_name,
                                   font=AppFonts.CAPTION,
                                   bg=team_info['colors'][0] if len(team_info['colors']) > 0 else '#3A3A3A',
                                   fg='white',
                                   relief='solid', bd=1,
                                   pady=6, padx=3,
                                   cursor='hand2',
                                   command=lambda t=team_name, c=team_info['city']: self._select_team(t, c))
                
                team_btn.grid(row=row, column=col, padx=1, pady=1, sticky='ew')
                
                # Configure grid weights for equal column widths
                team_grid.grid_columnconfigure(col, weight=1)
                
                # Store team button reference
                self.team_cards[team_name] = team_btn
                
    def _create_game_options(self, parent):
        """Create comprehensive game setup options"""
        options_frame = SectionCard(parent, text="  Game Setup Options  ",
                                     font=AppFonts.H2,
                                     bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        options_frame.pack(fill='x', padx=20, pady=20)
        
        # Create options in a grid layout
        options_grid = tk.Frame(options_frame, bg=AppColors.BG_ELEVATED)
        options_grid.pack(fill='x', padx=20, pady=20)
        
        # Database Size
        self._create_option_row(options_grid, 0, "Database Size:",
                               self.setup_options['database_size'],
                               ["Minimal (8 Teams)", "Small (16 Teams)", "Full Database (32 Teams)", "Extended (40+ Teams)"],
                               "Choose the number of teams and depth of player database")
        
        # Start Date
        self._create_option_row(options_grid, 1, "Season Start Date:",
                               self.setup_options['start_date'],
                               ["August 1, 2024", "September 1, 2024", "October 1, 2024", "November 1, 2024"],
                               "When should the season begin? Earlier start = longer pre-season")
        
        # Season Length
        self._create_option_row(options_grid, 2, "Season Length:",
                               self.setup_options['season_length'],
                               ["Short Season (20 Games)", "Half Season (41 Games)", "Full Season (82 Games)", "Extended Season (100 Games)"],
                               "How many regular season games per team?")
        
        # Difficulty
        self._create_option_row(options_grid, 3, "Difficulty:",
                               self.setup_options['difficulty'],
                               ["Rookie", "Amateur", "Professional", "Realistic", "Hall of Fame"],
                               "Affects AI intelligence, trade difficulty, and player development")
        
        # Advanced Options
        advanced_frame = SectionCard(options_frame, text="  Advanced Options  ",
                                      font=AppFonts.H3,
                                      bg=AppColors.BG_ELEVATED, fg=AppColors.WARNING)
        advanced_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        # Checkbox options
        checkbox_frame = tk.Frame(advanced_frame, bg=AppColors.BG_ELEVATED)
        checkbox_frame.pack(fill='x', padx=20, pady=15)
        
        # Create checkboxes in 2 columns
        self._create_checkbox_option(checkbox_frame, 0, 0, "Fantasy Draft", 
                                    self.setup_options['fantasy_draft'],
                                    "Redistribute all players among teams before season start")
        
        self._create_checkbox_option(checkbox_frame, 0, 1, "Salary Cap", 
                                    self.setup_options['salary_cap'],
                                    "Enable realistic salary cap management ($83.5M)")
        
        self._create_checkbox_option(checkbox_frame, 1, 0, "Injuries", 
                                    self.setup_options['injuries'],
                                    "Enable player injuries and recovery system")
        
        self._create_checkbox_option(checkbox_frame, 1, 1, "Morale System", 
                                    self.setup_options['morale_system'],
                                    "Enable player morale and team chemistry effects")
        
    def _create_option_row(self, parent, row, label_text, var, values, tooltip):
        """Create an option row with label, combobox, and tooltip"""
        # Label
        label = tk.Label(parent, text=label_text,
                        font=AppFonts.SMALL_BOLD,
                        bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        label.grid(row=row, column=0, sticky='w', padx=(0, 20), pady=10)
        
        # Combobox
        combo = ttk.Combobox(parent, textvariable=var,
                           values=values, state='readonly',
                           font=AppFonts.SMALL, width=25)
        combo.grid(row=row, column=1, sticky='w', pady=10)
        
        # Tooltip (as small label)
        tooltip_label = tk.Label(parent, text=tooltip,
                               font=AppFonts.CAPTION,
                               bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                               wraplength=300, justify='left')
        tooltip_label.grid(row=row, column=2, sticky='w', padx=(20, 0), pady=10)
        
    def _create_checkbox_option(self, parent, row, col, text, var, tooltip):
        """Create a checkbox option with tooltip"""
        frame = tk.Frame(parent, bg=AppColors.BG_ELEVATED)
        frame.grid(row=row, column=col, sticky='w', padx=(0, 40), pady=5)
        
        checkbox = tk.Checkbutton(frame, text=text, variable=var,
                                 font=AppFonts.SMALL,
                                 bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY,
                                 selectcolor='#2A2A2A',
                                 activebackground='#2A2A2A')
        checkbox.pack(anchor='w')
        
        tooltip_label = tk.Label(frame, text=tooltip,
                               font=AppFonts.CAPTION,
                               bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                               wraplength=200, justify='left')
        tooltip_label.pack(anchor='w', padx=(20, 0))
        
    def _create_load_game_tab(self):
        """Create load game tab"""
        load_frame = tk.Frame(self.notebook, bg=AppColors.BG_ELEVATED)
        self.notebook.add(load_frame, text="Load Game")
        
        # Save games list
        saves_frame = SectionCard(load_frame, text="  Your Save Games  ",
                                   font=AppFonts.H2,
                                   bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        saves_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Treeview for saves
        tree_frame = tk.Frame(saves_frame, bg=AppColors.BG_ELEVATED)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        self.saves_tree = ttk.Treeview(tree_frame,
                                      columns=('date', 'team', 'season'),
                                      show='headings',
                                      height=15)
        
        self.saves_tree.heading('#1', text='Save Name')
        self.saves_tree.heading('date', text='Last Modified')
        self.saves_tree.heading('team', text='Team')
        self.saves_tree.heading('season', text='Season/Date')
        
        self.saves_tree.column('#1', width=250)
        self.saves_tree.column('date', width=150)
        self.saves_tree.column('team', width=200)
        self.saves_tree.column('season', width=150)
        
        # Scrollbar for saves
        saves_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                       command=self.saves_tree.yview)
        self.saves_tree.configure(yscrollcommand=saves_scrollbar.set)
        
        self.saves_tree.pack(side='left', fill='both', expand=True)
        saves_scrollbar.pack(side='right', fill='y')
        
        # Bind events
        self.saves_tree.bind('<<TreeviewSelect>>', self._on_save_select)
        self.saves_tree.bind('<Double-1>', self._load_selected_save)
        
        # Load game buttons
        btn_frame = tk.Frame(saves_frame, bg=AppColors.BG_ELEVATED)
        btn_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        load_btn = tk.Button(btn_frame, text="Load Selected Game",
                           bg=AppColors.ACCENT, fg='white',
                           font=AppFonts.BODY_BOLD, relief='flat', bd=0,
                           pady=10, padx=25, cursor='hand2',
                           command=self._load_selected_save)
        load_btn.pack(side='left', padx=(0, 15))
        
        delete_btn = tk.Button(btn_frame, text="Delete",
                             bg='#DA3633', fg='white',
                             font=AppFonts.SMALL, relief='flat', bd=0,
                             pady=8, padx=20, cursor='hand2',
                             command=self._delete_selected_save)
        delete_btn.pack(side='left', padx=(0, 15))
        
        import_btn = tk.Button(btn_frame, text="Import Save",
                             bg=AppColors.ACCENT_DIM, fg='white',
                             font=AppFonts.SMALL, relief='flat', bd=0,
                             pady=8, padx=20, cursor='hand2',
                             command=self._import_save)
        import_btn.pack(side='left')
        
    def _create_settings_tab(self):
        """Create settings tab"""
        settings_frame = tk.Frame(self.notebook, bg=AppColors.BG_ELEVATED)
        self.notebook.add(settings_frame, text="Settings")
        
        # Settings content
        settings_content = SectionCard(settings_frame, text="  Launcher Settings  ",
                                       font=AppFonts.H2,
                                       bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_PRIMARY)
        settings_content.pack(fill='x', padx=20, pady=20)
        
        # Placeholder for future settings
        tk.Label(settings_content,
                text="Launcher settings and preferences will be available here.\nGame settings can be configured in-game.",
                font=AppFonts.BODY,
                bg=AppColors.BG_ELEVATED, fg=AppColors.TEXT_SECONDARY,
                justify='center').pack(pady=40)
        
    def _create_footer(self, parent):
        """Create enhanced footer"""
        footer_frame = tk.Frame(parent, bg=AppColors.BG_ELEVATED, height=50)
        footer_frame.pack(fill='x', side='bottom')
        footer_frame.pack_propagate(False)
        
        # Status and info
        info_frame = tk.Frame(footer_frame, bg=AppColors.BG_ELEVATED)
        info_frame.pack(side='left', fill='y', padx=20)
        
        self.status_label = tk.Label(info_frame, text="Ready to manage your hockey dynasty",
                                   font=AppFonts.SMALL,
                                   bg=AppColors.BG_ELEVATED, 
                                   fg=AppColors.TEXT_SECONDARY)
        self.status_label.pack(anchor='w', pady=15)
        
        # Exit button
        exit_btn = tk.Button(footer_frame, text="Exit",
                           font=AppFonts.LABEL,
                           bg='#DA3633', fg='white',
                           relief='flat', bd=0, pady=8, padx=20,
                           cursor='hand2',
                           command=self._on_closing)
        exit_btn.pack(side='right', padx=20, pady=10)
        
    # Team Selection Methods
    def _select_team(self, team_name, city):
        """Select a specific team"""
        self.selected_team = {'name': team_name, 'city': city}
        
        # Update UI
        self.selected_team_label.config(
            text=f"{team_name}\n{city}",
            fg=AppColors.SUCCESS
        )
        self.selected_team_frame.config(bg=AppColors.BG_ELEVATED, relief='solid', bd=2)
        
        # Check readiness
        self._check_readiness()
        
        # Update button states
        for name, btn in self.team_cards.items():
            if name == team_name:
                btn.config(relief='solid', bd=3)
            else:
                btn.config(relief='solid', bd=1)
        
        self.status_label.config(text=f"Team selected: {team_name}")
        
    def _select_random_team(self):
        """Select a random team"""
        all_teams = []
        for division in self.nhl_teams.values():
            for team_name, info in division.items():
                all_teams.append((team_name, info['city']))
        
        if all_teams:
            team_name, city = random.choice(all_teams)
            self._select_team(team_name, city)
            
    # Game Setup Methods
    def _open_setup_wizard(self):
        """Open the new-game setup wizard (Quick Start / Custom Setup).

        On completion the wizard config takes precedence over this tab's own
        options when the game starts.
        """
        from new_game_setup import open_setup_wizard

        holder = {}

        def _on_done(cfg):
            holder['config'] = cfg
            self.wizard_config = cfg
            # Reflect the wizard's team choice in the launcher UI
            team_name = cfg.get('user_team')
            if team_name:
                self.selected_team = {'name': team_name, 'city': ''}
            self._check_game_readiness()
            try:
                self.status_label.config(
                    text=f"Wizard: {team_name} • {cfg.get('database_size', '').capitalize()} database")
            except Exception:
                pass

        wiz = open_setup_wizard(self, _on_done)
        self.wait_window(wiz)

    def _start_new_game(self):
        """Start new game with current settings"""
        print("START GAME button clicked!")
        print(f"Selected team: {self.selected_team}")
        
        if not self.selected_team:
            print("No team selected")
            messagebox.showwarning("No Team Selected", 
                                 "Please select a team before starting the game.")
            return
        
        print("Team validation passed")
        
        try:
            # Show starting message with options
            options = []
            if self.setup_options['fantasy_draft'].get():
                options.append("Fantasy Draft")
            if not self.setup_options['salary_cap'].get():
                options.append("No Salary Cap")
            
            options_text = " • ".join(options) if options else "Standard Settings"
            
            self.status_label.config(
                text=f"Starting: {self.selected_team['name']} • {self.setup_options['database_size'].get()} • {options_text}"
            )
            self.update()
            
            # Start the game
            print("Calling _start_main_game()...")
            self._start_main_game()
            
        except Exception as e:
            print(f"Exception in _start_new_game: {e}")
            messagebox.showerror("Error", f"Failed to start game:\n{str(e)}")
            
    def _start_main_game(self):
        """Start the main game application with all configurations"""
        try:
            print("Starting main game...")
            
            # Hide launcher but don't quit yet - we need it alive until new root is created
            self.withdraw()
            
            print("Importing main modules...")
            from main import GameManager, HockeyManagerGUI
            from game_classes import GMProfile
            print("Modules imported successfully")
            
            # Create game manager with advanced settings
            print("Creating GameManager...")
            gm = GameManager()
            print("GameManager created successfully")
            
            # Prepare startup settings
            print("Preparing startup settings...")
            startup_settings = {}
            
            # Create GM Profile
            if self.gm_profile['name'].get().strip():
                gm_profile = GMProfile(
                    name=self.gm_profile['name'].get(),
                    age=int(self.gm_profile['age'].get()),
                    former_player=self.gm_profile['background'].get() == "Former Player",
                    coaching_experience=self.gm_profile['background'].get() == "Former Coach",
                    management_style=self.gm_profile['management_style'].get(),
                    # Additional fields for complete profile
                    risk_tolerance=self.gm_profile.get('risk_tolerance', tk.StringVar()).get() or "Moderate",
                    loyalty_to_players=self.gm_profile.get('loyalty', tk.StringVar()).get() or "Medium"
                )
                
                startup_settings['gm_profile'] = gm_profile
                print(f"GM Profile created: {gm_profile.name} ({gm_profile.age} years old)")
            
            # Set selected team
            if self.selected_team:
                startup_settings['user_team'] = self.selected_team['name']
                print(f"Team selected: {self.selected_team['name']}")
            
            # Apply advanced game settings
            # Extract just the size name from display string (e.g. "Small (8K players, 32 NHL+AHL teams)" -> "Small")
            db_size_full = self.setup_options['database_size'].get()
            db_size_name = db_size_full.split(' ')[0] if ' ' in db_size_full else db_size_full
            
            startup_settings.update({
                'database_size': db_size_name,
                'start_date': self.setup_options['start_date'].get(),
                'season_length': self.setup_options['season_length'].get(),
                'difficulty': self.setup_options['difficulty'].get(),
                'fantasy_draft': self.setup_options['fantasy_draft'].get(),
                'salary_cap': self.setup_options['salary_cap'].get(),
                'injuries': self.setup_options['injuries'].get(),
                'morale_system': self.setup_options['morale_system'].get(),
                'realistic_progression': self.setup_options['realistic_progression'].get(),
                'trade_difficulty': self.setup_options['trade_difficulty'].get(),
                'cpu_gm_intelligence': self.setup_options['cpu_gm_intelligence'].get(),
                'international_players': self.setup_options['international_players'].get(),
                'selected_team': self.selected_team['name'] if self.selected_team else None
            })
            
            # Setup wizard takes precedence when the user completed it: it
            # carries league selection, fog of war, and per-league sim detail
            # that this tab does not offer.
            if self.wizard_config:
                from new_game_setup import build_database_config
                cfg = self.wizard_config
                startup_settings.update({
                    'database_size': cfg['database_size'].capitalize(),
                    'database_config': build_database_config(cfg),
                    'user_team': cfg['user_team'],
                    'selected_team': cfg['user_team'],
                    'user_league': cfg.get('user_league', 'NHL'),
                    'gm_name': cfg.get('gm_name', 'General Manager'),
                    'fog_of_war': cfg.get('fog_of_war', True),
                    'sim_detail': cfg.get('sim_detail', {}) or {},
                })
                print(f"Setup wizard config applied: {cfg['user_team']}")

            # Store settings in game manager
            gm.startup_settings = startup_settings
            
            # User team will be set by apply_all_game_settings using 'selected_team' parameter
            
            print("Advanced game settings configured:")
            for setting, value in startup_settings.items():
                if setting not in ['gm_profile', 'user_team']:
                    print(f"   {setting}: {value}")
            
            # Apply fantasy draft if selected
            if self.setup_options['fantasy_draft'].get():
                print("Fantasy draft will be conducted after game initialization...")
            
            # Apply startup settings to game manager
            print("Applying startup settings to GameManager...")
            gm.apply_startup_settings(startup_settings)
            print("Startup settings applied successfully")
            
            # Verify user team was set properly
            if hasattr(gm, 'user_team') and gm.user_team:
                print(f"User team verified: {gm.user_team.team_name}")
            else:
                print("User team not set properly")
            
            # Create and start the main game application
            print("Creating HockeyManagerGUI...")
            app = HockeyManagerGUI(gm)
            app.startup_settings = startup_settings
            app._update_game_viewer_button_state()
            print("HockeyManagerGUI created successfully")
            
            # Don't destroy the old launcher yet - it can cause Tk root issues
            # Just ensure the new app is in front
            print("Hiding launcher window...")
            # self.destroy()  # Don't destroy - causes "no default root" errors
            
            print("Starting main game loop...")
            app.mainloop()
            
            # Now destroy the launcher after game exits
            try:
                self.destroy()
            except:
                pass
            
            print("Game completed normally")
            # Exit cleanly after game finishes
            sys.exit(0)
            
        except Exception as e:
            print(f"Game startup error: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to start game:\n{str(e)}")
            self.deiconify()  # Show launcher again on error
    
    def _register_widgets(self):
        """Register all UI widgets for direct access during updates"""
        try:
            # Find and register widgets in each main frame
            if hasattr(self, 'setup_frame'):
                self._register_widgets_in_frame(self.setup_frame, 'game_setup')
            if hasattr(self, 'profile_frame'):
                self._register_widgets_in_frame(self.profile_frame, 'gm_profile') 
            if hasattr(self, 'team_frame'):
                self._register_widgets_in_frame(self.team_frame, 'team_selection')
            
            print(f"Registered {sum(len(cat) for cat in self.ui_widgets.values())} widgets")
            
        except Exception as e:
            print(f"Widget registration error: {e}")

    def _register_widgets_in_frame(self, frame, category):
        """Recursively register widgets in a frame"""
        if not frame or not hasattr(frame, 'winfo_children'):
            return
            
        for child in frame.winfo_children():
            try:
                widget_type = child.winfo_class()
                
                if widget_type in ['Entry', 'TCombobox', 'Combobox']:
                    # Get the associated StringVar if any
                    try:
                        textvariable = child.cget('textvariable') if hasattr(child, 'cget') else None
                        if textvariable:
                            var_name = str(textvariable).split('.')[-1]  # Extract variable name
                            self.ui_widgets[category][var_name] = child
                    except:
                        pass
                        
                elif widget_type in ['Listbox', 'Treeview']:
                    self.ui_widgets[category][f'list_{len(self.ui_widgets[category])}'] = child
                    
                # Recursively check child frames
                if hasattr(child, 'winfo_children'):
                    self._register_widgets_in_frame(child, category)
                    
            except Exception as e:
                continue  # Skip problematic widgets

    def _force_stringvar_refresh(self):
        """Force StringVars to re-trigger their widget bindings"""
        try:
            print("Forcing StringVar refresh to trigger widget updates...")
            
            # Force GM profile StringVars to re-trigger their bindings
            for key, var in self.gm_profile.items():
                if hasattr(var, 'get') and hasattr(var, 'set'):
                    current_val = var.get()
                    # Clear and re-set to force binding refresh
                    var.set("")
                    self.update_idletasks()  # Process the clear
                    var.set(current_val)
                    self.update_idletasks()  # Process the new value
                    print(f"  • Refreshed GM {key}: {current_val}")
            
            # Force setup options StringVars to re-trigger their bindings
            for key, var in self.setup_options.items():
                if hasattr(var, 'get') and hasattr(var, 'set'):
                    current_val = var.get()
                    # For BooleanVar, use different approach
                    if isinstance(var, tk.BooleanVar):
                        var.set(not current_val)
                        self.update_idletasks()
                        var.set(current_val)
                        self.update_idletasks()
                    else:
                        # For StringVar
                        var.set("")
                        self.update_idletasks()
                        var.set(current_val)
                        self.update_idletasks()
                    print(f"  • Refreshed setup {key}: {current_val}")
            
            print("StringVar refresh completed")
            
        except Exception as e:
            print(f"StringVar refresh error: {e}")

    def _force_ui_refresh(self):
        """Comprehensive UI refresh that forces all widgets to update visually"""
        try:
            print("Starting comprehensive UI refresh...")
            
            # 1. Process all pending UI events first
            self.update_idletasks()
            
            # 2. Force StringVar access to trigger widget updates
            for key, var in self.setup_options.items():
                if hasattr(var, 'get'):
                    current_val = var.get()
                    # Force re-set to trigger widget refresh
                    var.set(current_val)
            
            for key, var in self.gm_profile.items():
                if hasattr(var, 'get'):
                    current_val = var.get()
                    # Force re-set to trigger widget refresh  
                    var.set(current_val)
            
            # 3. Force notebook tab refresh
            if hasattr(self, 'notebook'):
                current_tab = self.notebook.select()
                # Force tab refresh by temporarily switching
                tab_count = self.notebook.index('end')
                if tab_count > 1:
                    for i in range(tab_count):
                        tab_id = self.notebook.tabs()[i]
                        self.notebook.select(tab_id)
                        self.update_idletasks()
                    # Return to original tab
                    if current_tab:
                        self.notebook.select(current_tab)
            
            # 4. Update main window
            self.update()
            
            # 5. Schedule additional refresh to ensure all widgets caught up
            self.after_idle(self._secondary_refresh)
            
            print("Comprehensive UI refresh completed")
            
        except Exception as e:
            print(f"UI refresh error: {e}")

    def _secondary_refresh(self):
        """Secondary refresh pass to catch any missed updates"""
        try:
            self.update_idletasks()
            
            # Force focus events which can trigger widget refreshes
            if hasattr(self, 'notebook'):
                current_tab = self.notebook.select()
                if current_tab:
                    # Get the tab content frame and force focus
                    try:
                        tab_frame = self.nametowidget(current_tab)
                        if tab_frame:
                            tab_frame.focus_set()
                            self.update_idletasks()
                    except:
                        pass
            
            print("Secondary refresh completed")
            
        except Exception as e:
            print(f"Secondary refresh error: {e}")

    def _force_widget_updates(self):
        """Directly update all widgets using stored references"""
        try:
            print("Starting direct widget updates...")
            
            # Update GM Profile widgets directly
            gm_widgets = [
                ('name_entry', self.gm_profile['name']),
                ('age_combo', self.gm_profile['age']),
                ('exp_combo', self.gm_profile['experience']),
                ('bg_combo', self.gm_profile['background']),
                ('style_combo', self.gm_profile['management_style']),
                ('contract_combo', self.gm_profile['contract_length']),
                ('rep_combo', self.gm_profile['reputation'])
            ]
            
            for widget_name, string_var in gm_widgets:
                try:
                    widget = getattr(self, widget_name, None)
                    if widget and hasattr(string_var, 'get'):
                        current_value = string_var.get()
                        
                        # Check widget type more precisely
                        widget_type = widget.winfo_class()
                        
                        if widget_type == 'Entry':
                            # Entry widget
                            widget.delete(0, 'end')
                            widget.insert(0, str(current_value))
                            print(f"  • Updated {widget_name}: {current_value}")
                        elif widget_type in ['TCombobox', 'Combobox'] or hasattr(widget, 'current'):
                            # Combobox widget - enhanced readonly handling
                            success = self._update_combobox_robust(widget, current_value, widget_name)
                            if success:
                                print(f"  • Updated {widget_name}: {current_value}")
                            else:
                                print(f"  Failed to update {widget_name}: {current_value}")
                        
                        # Force widget refresh
                        widget.update_idletasks()
                        widget.update()
                        
                except Exception as e:
                    print(f"  Error updating {widget_name}: {e}")
                    continue
            
            # Update game setup checkboxes and comboboxes by finding them
            self._update_setup_widgets()
            
            print("Direct widget updates completed")
            
        except Exception as e:
            print(f"Widget update error: {e}")
            
    def _update_combobox_robust(self, combobox, value, widget_name=""):
        """Robust method to update Combobox widgets, especially readonly ones"""
        try:
            # CRITICAL: For readonly Combobox with textvariable, we MUST set the current() index
            # Setting StringVar alone won't make the widget display the value
            
            if hasattr(combobox, 'cget') and combobox.cget('state') == 'readonly':
                # Method for readonly: Find the index and use current()
                try:
                    values = combobox.cget('values')
                    str_value = str(value)
                    
                    if str_value in values:
                        # Value exists in the list - set the index
                        index = list(values).index(str_value)
                        combobox.current(index)
                        
                        # Force widget update
                        combobox.update_idletasks()
                        
                        # Verify it worked
                        display_value = combobox.get()
                        return str(display_value) == str_value
                    else:
                        # Value not in combobox values - this shouldn't happen with proper setup
                        return False
                        
                except Exception as e:
                    return False
                    
            else:
                # Method for normal state comboboxes: Direct set
                try:
                    combobox.set(str(value))
                    combobox.update_idletasks()
                    
                    # Verify it worked
                    display_value = combobox.get()
                    return str(display_value) == str(value)
                        
                except Exception as e:
                    return False
                    
        except Exception as e:
            return False
            
    def _update_setup_widgets(self):
        """Find and update game setup widgets"""
        try:
            if hasattr(self, 'notebook'):
                # Get the advanced setup tab
                for tab_id in self.notebook.tabs():
                    tab_text = self.notebook.tab(tab_id, 'text')
                    if 'Advanced' in tab_text or 'Setup' in tab_text:
                        tab_frame = self.nametowidget(tab_id)
                        self._update_widgets_in_frame(tab_frame)
                        break
        except Exception as e:
            print(f"  Error updating setup widgets: {e}")
            
    def _update_widgets_in_frame(self, frame):
        """Recursively update widgets in a frame"""
        if not frame or not hasattr(frame, 'winfo_children'):
            return
            
        for child in frame.winfo_children():
            try:
                widget_type = child.winfo_class()
                
                if widget_type in ['TCombobox', 'Combobox']:
                    # Try to get the textvariable and update
                    try:
                        textvariable = child.cget('textvariable')
                        if textvariable:
                            # Get the StringVar name and find it in setup_options
                            var_name = str(textvariable).split('.')[-1]
                            for option_name, option_var in self.setup_options.items():
                                if str(option_var).split('.')[-1] == var_name:
                                    current_value = option_var.get()
                                    child.set(current_value)
                                    # For readonly comboboxes, also set current index
                                    if child.cget('state') == 'readonly':
                                        try:
                                            values = child.cget('values')
                                            if str(current_value) in values:
                                                index = list(values).index(str(current_value))
                                                child.current(index)
                                        except:
                                            pass
                                    print(f"  • Updated setup option {option_name}: {current_value}")
                                    break
                    except:
                        pass
                        
                elif widget_type == 'Checkbutton':
                    # Handle checkboxes
                    try:
                        variable = child.cget('variable')
                        if variable:
                            var_name = str(variable).split('.')[-1] 
                            for option_name, option_var in self.setup_options.items():
                                if str(option_var).split('.')[-1] == var_name:
                                    # Force checkbox to refresh by toggling
                                    current_value = option_var.get()
                                    child.deselect()
                                    if current_value:
                                        child.select()
                                    print(f"  • Updated checkbox {option_name}: {current_value}")
                                    break
                    except:
                        pass
                
                # Recursively check child frames
                if hasattr(child, 'winfo_children'):
                    self._update_widgets_in_frame(child)
                    
            except Exception as e:
                continue

    def _final_refresh_pass(self):
        """Final refresh pass to ensure all UI elements are updated"""
        try:
            # Force a complete redraw of the entire window
            self.update()
            
            # Trigger validation events on GM profile widgets using stored references
            gm_widget_refs = ['name_entry', 'age_combo', 'exp_combo', 'bg_combo', 'style_combo', 'contract_combo', 'rep_combo']
            for widget_name in gm_widget_refs:
                try:
                    widget = getattr(self, widget_name, None)
                    if widget:
                        widget.event_generate('<FocusIn>')
                        widget.event_generate('<FocusOut>')
                        widget.update_idletasks()
                except:
                    continue
            
            # Force notebook to refresh its display
            if hasattr(self, 'notebook'):
                self.notebook.update_idletasks()
                self.notebook.update()
            
            print("Final refresh pass completed")
            
        except Exception as e:
            print(f"Final refresh error: {e}")
            
    def _cycle_notebook_tabs(self):
        """Cycle through notebook tabs to force visual refresh"""
        try:
            if hasattr(self, 'notebook'):
                current_tab = self.notebook.select()
                tab_count = self.notebook.index('end')
                
                # Quickly cycle through all tabs
                for i in range(tab_count):
                    tab_id = self.notebook.tabs()[i]
                    self.notebook.select(tab_id)
                    self.update_idletasks()
                
                # Return to original tab
                if current_tab:
                    self.notebook.select(current_tab)
                    self.update_idletasks()
                    
                print("Notebook tab cycling completed")
                
        except Exception as e:
            print(f"Tab cycling error: {e}")
            
    def _initialize_default_values(self):
        """Initialize default values and ensure widgets display them properly"""
        try:
            print("Forcing widget display of pre-assigned default values...")
            
            # All GM profile fields now have proper random defaults from initialization
            # Just force widgets to display their current StringVar values
            self._force_initial_widget_display()
            
            # Update GM profile preview
            self._update_gm_preview()
            
            print("Default values displayed in widgets successfully")
            
        except Exception as e:
            print(f"Default initialization error: {e}")
            
    def _force_initial_widget_display(self):
        """Force all widgets to display their initial StringVar values"""
        try:
            # GM Profile widgets - force display of current values
            gm_widgets = [
                ('name_entry', self.gm_profile['name']),
                ('age_combo', self.gm_profile['age']),
                ('exp_combo', self.gm_profile['experience']),
                ('bg_combo', self.gm_profile['background']),
                ('style_combo', self.gm_profile['management_style']),
                ('contract_combo', self.gm_profile['contract_length']),
                ('rep_combo', self.gm_profile['reputation'])
            ]
            
            for widget_name, string_var in gm_widgets:
                try:
                    widget = getattr(self, widget_name, None)
                    if widget and hasattr(string_var, 'get'):
                        current_value = string_var.get()
                        
                        if hasattr(widget, 'delete') and hasattr(widget, 'insert'):
                            # Entry widget - clear and insert current value
                            widget.delete(0, 'end')
                            widget.insert(0, str(current_value))
                        elif hasattr(widget, 'set'):
                            # Combobox widget - use robust update method
                            success = self._update_combobox_robust(widget, current_value, widget_name)
                            if success:
                                print(f"  • Initialized {widget_name}: {current_value}")
                            else:
                                print(f"  Failed to initialize {widget_name}: {current_value}")
                        
                        # Force immediate update
                        widget.update_idletasks()
                        
                except Exception as e:
                    print(f"  Error initializing {widget_name}: {e}")
                    continue
            
            # Force update of setup option widgets too
            self._force_setup_option_display()
            
        except Exception as e:
            print(f"Initial widget display error: {e}")
    
    def _force_combobox_initialization(self):
        """Force Combobox widgets to display their StringVar values after a delay."""
        print("\n=== Force Combobox Initialization ===")
        
        # Direct Combobox value assignment for GM profile
        combobox_mappings = [
            ('age_combo', self.gm_profile['age']),
            ('exp_combo', self.gm_profile['experience']),
            ('bg_combo', self.gm_profile['background']),
            ('style_combo', self.gm_profile['management_style']),
            ('rep_combo', self.gm_profile['reputation']),
            ('contract_combo', self.gm_profile['contract_length'])
        ]
        
        for widget_name, string_var in combobox_mappings:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                current_value = string_var.get()
                print(f"Force setting {widget_name} to '{current_value}'")
                
                try:
                    # Method 1: Try using current() if value exists in values list
                    if hasattr(widget, 'configure') and 'values' in widget.keys():
                        values = list(widget['values'])
                        if current_value in values:
                            index = values.index(current_value)
                            widget.current(index)
                            print(f"  → Set index {index} using current() method")
                            continue
                    
                    # Method 2: Temporarily enable, set value, disable
                    original_state = widget['state']
                    widget.configure(state='normal')
                    widget.set(current_value)
                    widget.configure(state=original_state)
                    print(f"  → Set using temporary state change")
                    
                    # Force widget refresh
                    widget.update()
                    widget.update_idletasks()
                    
                except Exception as e:
                    print(f"  → Error: {e}")
            else:
                print(f"Widget {widget_name} not found")
        
        # Final debug check
        print("\nFinal widget states after force initialization:")
        for widget_name, string_var in combobox_mappings:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                displayed_value = widget.get() if hasattr(widget, 'get') else 'N/A'
                stringvar_value = string_var.get()
                print(f"  {widget_name}: displayed='{displayed_value}', stringvar='{stringvar_value}'")
    
    def _force_setup_option_display(self):
        """Force setup option widgets to display their current values"""
        try:
            if hasattr(self, 'notebook'):
                # Find and update all setup option widgets
                for tab_id in self.notebook.tabs():
                    try:
                        tab_frame = self.nametowidget(tab_id)
                        self._initialize_widgets_in_frame(tab_frame)
                    except:
                        continue
                        
        except Exception as e:
            print(f"Setup option display error: {e}")
            
    def _initialize_widgets_in_frame(self, frame):
        """Recursively initialize widgets in a frame with their StringVar values"""
        if not frame or not hasattr(frame, 'winfo_children'):
            return
            
        for child in frame.winfo_children():
            try:
                widget_type = child.winfo_class()
                
                if widget_type in ['TCombobox', 'Combobox']:
                    # Get textvariable and set the widget to show its value
                    try:
                        textvariable = child.cget('textvariable')
                        if textvariable:
                            # Find the corresponding StringVar and get its value
                            var_name = str(textvariable).split('.')[-1]
                            for option_name, option_var in self.setup_options.items():
                                if str(option_var).split('.')[-1] == var_name:
                                    current_value = option_var.get()
                                    child.set(current_value)
                                    # For readonly comboboxes, also set current index
                                    if child.cget('state') == 'readonly':
                                        try:
                                            values = child.cget('values')
                                            if str(current_value) in values:
                                                index = list(values).index(str(current_value))
                                                child.current(index)
                                        except:
                                            pass
                                    child.update_idletasks()
                                    break
                    except:
                        pass
                        
                elif widget_type == 'Checkbutton':
                    # Force checkboxes to show their current state
                    try:
                        variable = child.cget('variable')
                        if variable:
                            var_name = str(variable).split('.')[-1]
                            for option_name, option_var in self.setup_options.items():
                                if str(option_var).split('.')[-1] == var_name:
                                    current_value = option_var.get()
                                    if current_value:
                                        child.select()
                                    else:
                                        child.deselect()
                                    child.update_idletasks()
                                    break
                    except:
                        pass
                
                # Recursively check child frames
                if hasattr(child, 'winfo_children'):
                    self._initialize_widgets_in_frame(child)
                    
            except Exception as e:
                continue

    def _check_readiness(self):
        """Check if all required setup is complete"""
        # Check for both start buttons (different tabs may have different button names)
        start_buttons = []
        if hasattr(self, 'start_button'):
            start_buttons.append(self.start_button)
        if hasattr(self, 'start_btn'):
            start_buttons.append(self.start_btn)
            
        if not start_buttons:
            return  # UI not ready yet
            
        ready = True
        reasons = []
        
        # Check GM profile requirements
        if not self.gm_profile['name'].get().strip():
            ready = False
            reasons.append("GM Name is required")
        
        try:
            age_str = self.gm_profile['age'].get()
            if age_str:
                age = int(age_str)
                if age < 25 or age > 70:
                    ready = False
                    reasons.append("GM Age must be between 25-70")
            else:
                ready = False
                reasons.append("GM Age must be selected")
        except (ValueError, TypeError):
            ready = False
            reasons.append("GM Age must be a valid number")
        
        # Check team selection
        if not self.selected_team:
            ready = False
            reasons.append("Team selection is required")
        
        # Check essential GM profile fields
        if not self.gm_profile['experience'].get():
            ready = False
            reasons.append("Experience level must be selected")
            
        if not self.gm_profile['background'].get():
            ready = False
            reasons.append("Background must be selected")
            
        if not self.gm_profile['management_style'].get():
            ready = False
            reasons.append("Management style must be selected")
            
        if not self.gm_profile['contract_length'].get():
            ready = False
            reasons.append("Contract length must be selected")
        
        # Update all start buttons
        for button in start_buttons:
            if ready:
                try:
                    button.configure(state='normal', bg=AppColors.ACCENT, fg='white')
                except:
                    pass
            else:
                try:
                    button.configure(state='disabled', bg=AppColors.BG_HOVER, fg=AppColors.TEXT_SECONDARY)
                except:
                    pass
        
        # Update status labels if they exist
        status_messages = {
            'ready': "All requirements complete - Ready to start your dynasty!",
            'partial': f"Missing requirements: {', '.join(reasons[:3])}{'...' if len(reasons) > 3 else ''}",
        }
        
        message = status_messages['ready'] if ready else status_messages['partial']
        color = '#4CBB17' if ready else '#FFB81C'
        
        # Update status labels
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
            
        if hasattr(self, 'ready_status_label'):
            self.ready_status_label.config(text=message, fg=color)
        
        # Console feedback (only when state changes)
        current_state = f"ready:{ready},reasons:{len(reasons)}"
        if not hasattr(self, '_last_validation_state') or self._last_validation_state != current_state:
            self._last_validation_state = current_state
            if ready:
                print("All setup complete - ready to start game!")
            else:
                print(f"Setup incomplete: {len(reasons)} issues remaining")
            
    # Save Game Methods
    def _load_save_games(self):
        """Load available save games"""
        self.save_games = []
        
        try:
            # Check multiple locations for save files
            save_locations = ['.', 'saves', 'save_games']
            save_extensions = ['.pdsave', '.save', '.sav', '.json']
            
            for location in save_locations:
                if not os.path.exists(location):
                    continue
                    
                for file in os.listdir(location):
                    if any(file.endswith(ext) for ext in save_extensions):
                        try:
                            file_path = os.path.join(location, file)
                            stat = os.stat(file_path)
                            modified = datetime.fromtimestamp(stat.st_mtime)
                            
                            save_info = {
                                'filename': file_path,
                                'display_name': file.split('.')[0],
                                'date': modified.strftime('%Y-%m-%d %H:%M'),
                                'team': 'Unknown',
                                'season': 'Unknown'
                            }
                            
                            self.save_games.append(save_info)
                        except:
                            pass
        except:
            pass
            
        self._populate_saves_list()
        
    def _populate_saves_list(self):
        """Populate saves list in the treeview"""
        if not hasattr(self, 'saves_tree'):
            return
            
        # Clear existing
        for item in self.saves_tree.get_children():
            self.saves_tree.delete(item)
            
        # Add saves
        sorted_saves = sorted(self.save_games, key=lambda x: x['date'], reverse=True)
        
        for save in sorted_saves:
            self.saves_tree.insert('', 'end',
                                 text=save['display_name'],
                                 values=(save['date'], save['team'], save['season']))
        
        # Select first save if available
        if sorted_saves:
            children = self.saves_tree.get_children()
            if children:
                self.saves_tree.selection_set(children[0])
                self.selected_save = sorted_saves[0]
                
    def _on_save_select(self, event):
        """Handle save selection"""
        selection = self.saves_tree.selection()
        if selection:
            item = selection[0]
            save_name = self.saves_tree.item(item, 'text')
            
            for save in self.save_games:
                if save['display_name'] == save_name:
                    self.selected_save = save
                    break
                    
    def _load_selected_save(self, event=None):
        """Load selected save game"""
        if not self.selected_save:
            messagebox.showwarning("No Selection", "Please select a save game.")
            return
            
        try:
            self.status_label.config(text=f"Loading {self.selected_save['display_name']}...")
            self.update()
            
            self._start_main_game()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load save:\n{str(e)}")
            
    def _load_specific_save(self, save_info):
        """Load a specific save from quick start"""
        self.selected_save = save_info
        self._load_selected_save()
        
    def _continue_last_game(self):
        """Continue most recent save"""
        if self.save_games:
            recent = sorted(self.save_games, key=lambda x: x['date'], reverse=True)[0]
            self.selected_save = recent
            self._load_selected_save()
        else:
            messagebox.showinfo("No Saves", "No save games found.")
            
    def _delete_selected_save(self):
        """Delete selected save"""
        if not self.selected_save:
            messagebox.showwarning("No Selection", "Please select a save game.")
            return
            
        result = messagebox.askyesno("Confirm Delete",
                                   f"Delete '{self.selected_save['display_name']}'?\n\n"
                                   "This cannot be undone.")
        if result:
            try:
                os.remove(self.selected_save['filename'])
                self._load_save_games()
                self.status_label.config(text="Save deleted")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete save:\n{str(e)}")
                
    def _import_save(self):
        """Import a save game file"""
        file_path = filedialog.askopenfilename(
            title="Import Save Game",
            filetypes=[
                ("Save Files", "*.pdsave *.save *.sav *.json"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            try:
                # Copy to saves directory
                import shutil
                if not os.path.exists('saves'):
                    os.makedirs('saves')
                    
                filename = os.path.basename(file_path)
                destination = os.path.join('saves', filename)
                shutil.copy2(file_path, destination)
                
                self._load_save_games()
                self.status_label.config(text=f"Imported: {filename}")
                messagebox.showinfo("Success", f"Save game imported successfully:\n{filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import save:\n{str(e)}")
                
    def _initialize_random_gm_defaults(self):
        """Initialize random default values for GM profile fields"""
        import random
        
        # Random GM names (mix of realistic and fun options)
        gm_names = [
            "Alex Johnson", "Sarah Williams", "Mike Davis", "Lisa Thompson", 
            "Chris Anderson", "Jennifer Miller", "David Wilson", "Amanda Brown",
            "Mark Garcia", "Jessica Martinez", "Robert Taylor", "Michelle Lee",
            "Jason White", "Laura Harris", "Kevin Clark", "Rachel Lewis"
        ]
        
        # Age range: realistic GM ages (typically 35-65)
        gm_ages = list(range(35, 66))
        
        # Experience levels
        experience_options = ["First-Time GM", "Assistant GM Experience", "Former GM", "Veteran Executive"]
        
        # Background types  
        background_options = ["Former Player", "Former Coach", "Former Scout", "Business Executive", "Analytics Expert"]
        
        # Management styles
        style_options = ["Players' GM", "Strict Disciplinarian", "Analytics-Focused", "Balanced", "Old-School"]
        
        # Reputation levels (start modest for new GMs)
        reputation_options = ["Unknown", "Rising Star", "Proven Executive"]
        
        # Contract lengths
        contract_options = ["1 Year (Prove It)", "2 Years", "3 Years", "4 Years", "5 Years (Long-term)"]
        
        # Assign random defaults
        self.default_gm_name = random.choice(gm_names)
        self.default_gm_age = random.choice(gm_ages)
        self.default_gm_experience = random.choice(experience_options)
        self.default_gm_background = random.choice(background_options) 
        self.default_gm_style = random.choice(style_options)
        self.default_gm_reputation = random.choice(reputation_options)
        self.default_gm_contract = random.choice(contract_options)
        
        print(f"Generated random GM profile:")
        print(f"  Name: {self.default_gm_name}")
        print(f"  Age: {self.default_gm_age}")
        print(f"  Experience: {self.default_gm_experience}")
        print(f"  Background: {self.default_gm_background}")
        print(f"  Style: {self.default_gm_style}")
        print(f"  Reputation: {self.default_gm_reputation}")
        print(f"  Contract: {self.default_gm_contract}")
                
    def _on_closing(self):
        """Handle window closing"""
        print("Enhanced launcher closing...")
        try:
            # Stop any running validation checks
            if hasattr(self, 'after_id'):
                self.after_cancel(self.after_id)
        except:
            pass
        
        # Clean shutdown
        self.quit()
        self.destroy()
        print("Enhanced launcher closed successfully")


def main():
    """Main entry point for enhanced launcher"""
    try:
        launcher = EnhancedPuckDynastyLauncher()
        launcher.mainloop()
    except Exception as e:
        messagebox.showerror("Launcher Error", f"Failed to start enhanced launcher:\n{str(e)}")


if __name__ == "__main__":
    main()