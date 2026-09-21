"""
Startup Window for Hockey Manager
Allows users to select their team and configure game settings before starting
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
import os
from tooltip import create_tooltip, DATABASE_TOOLTIPS

# Try to import PIL for image support
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL not available - background images will be disabled")
    print("To enable background images, install Pillow: pip install Pillow")

class StartupWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏒 Puck Dynasty - Hockey Management Simulator")
        self.geometry("1400x900")  # Larger default size
        self.configure(bg='#0a0a0a')  # Deeper black for modern look
        self.resizable(True, True)
        self.minsize(1200, 800)  # Minimum size constraint
        
        # Game settings to be passed to GameManager
        self.game_settings = None
        self.selected_team = None
        
        # Try to load background image
        self.background_image = None
        self.background_photo = None
        self._load_background_image()
        
        # Set application icon
        self._set_application_icon()
        
        # Create the UI
        self._create_ui()
        
        # Center the window
        self._center_window()
        
        # Override window close to clean up properly
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _load_background_image(self):
        """Load custom background image if available"""
        # Try to load background - if it fails, we'll fall back gracefully
        if not PIL_AVAILABLE:
            print("PIL not available - using solid background")
            return
        
        if not PIL_AVAILABLE:
            print("PIL not available - skipping background image loading")
            return
            
        # Look for background image in multiple locations
        possible_paths = [
            "background.jpg", "background.png", "bg.jpg", "bg.png",
            "assets/background.jpg", "assets/background.png", 
            "images/background.jpg", "images/background.png",
            "hockey_bg.jpg", "hockey_bg.png", "rink.jpg", "rink.png"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    # Load and resize image
                    pil_image = Image.open(path)
                    # Resize to fit window while maintaining aspect ratio
                    pil_image = pil_image.resize((1000, 700), Image.Resampling.LANCZOS)
                    # Store image reference properly to prevent garbage collection
                    self.background_image = pil_image  # Keep PIL image reference
                    
                    # Create PhotoImage without custom name to avoid conflicts
                    self.background_photo = ImageTk.PhotoImage(pil_image)
                    print(f"Loaded background image: {path}")
                    return
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
                    continue
        
        print("No background image found. Using default styling.")
        print("To add a background image, place an image file named 'background.jpg', 'background.png', 'hockey_bg.jpg', etc. in the game folder.")
    
    def _set_application_icon(self):
        """Set the Puck Dynasty logo as the application icon"""
        try:
            import os
            # Get the path to the logo file
            logo_path = os.path.join(os.path.dirname(__file__), "PUCK DYNASTY LOGO.png")
            
            if os.path.exists(logo_path):
                # Load and set the icon using PIL if available
                if PIL_AVAILABLE:
                    from PIL import Image, ImageTk
                    
                    # Load the image and resize it for icon use
                    icon_image = Image.open(logo_path)
                    # Resize to standard icon sizes (keeping aspect ratio)
                    icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    self.icon_photo = ImageTk.PhotoImage(icon_image)
                    
                    # Set as window icon
                    self.iconphoto(True, self.icon_photo)
                    
                    print("✅ Puck Dynasty logo set as startup window icon")
                else:
                    print("⚠️ PIL not available for icon, using text icon")
                    self.title("🏒 Puck Dynasty - New Game Setup")
            else:
                print(f"⚠️ Logo file not found at: {logo_path}")
                # Set a text-based icon as fallback
                self.title("🏒 Puck Dynasty - New Game Setup")
                
        except Exception as e:
            print(f"⚠️ Error setting startup icon: {e}")
            self.title("🏒 Puck Dynasty - New Game Setup")

    def _center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_ui(self):
        """Create the main UI with modern, clean design"""
        # Main container with modern gradient-style background
        main_frame = tk.Frame(self, bg='#0a0a0a')
        main_frame.pack(fill="both", expand=True)
        
        # Professional modern color palette
        self.colors = {
            'bg_primary': '#0F0F0F',      # Rich deep black
            'bg_secondary': '#1A1A1A',    # Dark charcoal  
            'bg_tertiary': '#242424',     # Medium charcoal
            'bg_card': '#1E1E1E',         # Card background
            'bg_elevated': '#2A2A2A',     # Elevated elements
            'accent_primary': '#0066CC',   # Professional blue
            'accent_secondary': '#004499', # Darker blue
            'accent_success': '#00AA44',   # Success green
            'accent_warning': '#FF8800',   # Warning orange
            'accent_danger': '#CC0000',    # Error red
            'accent_gold': '#FFB000',      # Premium gold
            'text_primary': '#FFFFFF',     # Pure white
            'text_secondary': '#B8B8B8',   # Light gray
            'text_muted': '#888888',       # Muted gray
            'text_accent': '#66B3FF',      # Accent text
            'border': '#333333',           # Border color
            'border_light': '#404040',     # Lighter borders
            'hover': '#2A2A2A',            # Hover state
            'hover_accent': '#0080FF',     # Accent hover
            'shadow': '#000000',           # Shadow color
            'gradient_start': '#1A1A1A',   # Gradient start
            'gradient_end': '#0F0F0F'      # Gradient end
        }
        
        # Always create the main content container, with or without background
        content_container = main_frame
        
        if self.background_photo:
            try:
                # Create canvas for background image
                self.bg_canvas = tk.Canvas(main_frame, highlightthickness=0, bg='#1e1e1e')
                self.bg_canvas.pack(fill="both", expand=True)
                
                # Test if we can use the image immediately
                test_label = tk.Label(self.bg_canvas, image=self.background_photo)
                test_label.destroy()  # If this works, the image is valid
                
                # Set background image to fill canvas
                self.bg_image_id = self.bg_canvas.create_image(500, 350, anchor="center", image=self.background_photo)
                print("Background image applied successfully")
                
                # Create semi-transparent overlay for better text readability
                overlay = tk.Frame(self.bg_canvas, bg='#000000')
                overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
                overlay.configure(bg='#000000')  # Semi-transparent black overlay
                
                content_container = overlay
                
            except (tk.TclError, AttributeError) as e:
                print(f"Background image error: {e}")
                # Fall back to solid background and clear the photo reference
                if hasattr(self, 'bg_canvas'):
                    self.bg_canvas.destroy()
                self.background_photo = None
                content_container = main_frame
                content_container.configure(bg='#1e1e1e')
        else:
            # No background image, use solid color
            content_container.configure(bg='#1e1e1e')
        
        # Create the main content in the container
        self._create_content(content_container)
    
    def _create_content(self, container):
        """Create a completely modern, professional startup interface"""
        
        # MODERN HEADER SECTION
        header_frame = tk.Frame(container, bg='#2c2c2c', height=140)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        # Header content with logo and title side by side
        header_content = tk.Frame(header_frame, bg='#2c2c2c')
        header_content.pack(expand=True, fill="both", padx=40, pady=20)
        
        # Logo section
        logo_section = tk.Frame(header_content, bg='#2c2c2c')
        logo_section.pack(side="left", anchor="w")
        
        if PIL_AVAILABLE and os.path.exists("PUCK DYNASTY LOGO.png"):
            try:
                logo_image = Image.open("PUCK DYNASTY LOGO.png")
                logo_image = logo_image.resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_image)
                logo_label = tk.Label(logo_section, image=self.logo_photo, bg='#2c2c2c')
                logo_label.pack(side="left")
            except Exception as e:
                print(f"Logo error: {e}")
        
        # Title section
        title_section = tk.Frame(header_content, bg='#2c2c2c')
        title_section.pack(side="left", anchor="w", padx=(20, 0), fill="y")
        
        title_label = tk.Label(title_section, 
                              text="PUCK DYNASTY", 
                              font=("Segoe UI", 32, "bold"), 
                              bg='#2c2c2c', fg='#ffffff')
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(title_section, 
                                 text="Professional Hockey Management", 
                                 font=("Segoe UI", 14), 
                                 bg='#2c2c2c', fg='#b0b0b0')
        subtitle_label.pack(anchor="w", pady=(5, 0))
        
        # NAVIGATION SECTION
        nav_frame = tk.Frame(container, bg='#3a3a3a', height=80)
        nav_frame.pack(fill="x")
        nav_frame.pack_propagate(False)
        
        nav_container = tk.Frame(nav_frame, bg='#3a3a3a')
        nav_container.pack(expand=True, pady=20)
        
        # Modern tab-style navigation
        self.nav_buttons = {}
        self.current_section = None
        
        nav_options = [
            ("SELECT TEAM", "Choose Your Franchise", self._show_team_selection),
            ("GM PROFILE", "Create Your Identity", self._show_gm_profile), 
            ("SETTINGS", "Configure Experience", self._show_game_settings)
        ]
        
        for i, (text, desc, command) in enumerate(nav_options):
            # Create modern tab button
            tab_frame = tk.Frame(nav_container, bg='#4a4a4a', relief='raised', bd=1)
            tab_frame.pack(side="left", padx=5)
            
            tab_button = tk.Button(tab_frame,
                                  text=f"{text}\n{desc}",
                                  command=command,
                                  font=("Segoe UI", 11, "bold"),
                                  bg='#4a4a4a',
                                  fg='#ffffff',
                                  activebackground='#0078d4',
                                  activeforeground='#ffffff',
                                  relief='flat',
                                  bd=0,
                                  padx=25,
                                  pady=15,
                                  cursor='hand2',
                                  justify='center')
            tab_button.pack()
            
            self.nav_buttons[text] = tab_frame
        
        # MAIN CONTENT AREA
        main_area = tk.Frame(container, bg='#2c2c2c')
        main_area.pack(fill="both", expand=True)
        
        # Content container with padding
        self.content_container = tk.Frame(main_area, bg='#3a3a3a', relief='sunken', bd=1)
        self.content_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Create section frames with dark background
        self.team_frame = tk.Frame(self.content_container, bg='#3a3a3a')
        self.gm_frame = tk.Frame(self.content_container, bg='#3a3a3a') 
        self.settings_frame = tk.Frame(self.content_container, bg='#3a3a3a')
        
        # Initialize content
        self._create_team_selection()
        self._create_gm_profile_tab()
        self._create_game_settings()
        
        # Show team selection by default
        self._show_team_selection()
        
        # BOTTOM ACTION BAR
        action_bar = tk.Frame(container, bg='#eeeeee', height=80)
        action_bar.pack(fill="x", side="bottom")
        action_bar.pack_propagate(False)
        
        # Action buttons container
        button_container = tk.Frame(action_bar, bg='#eeeeee')
        button_container.pack(expand=True, pady=20)
        
        # Cancel button - modern style
        cancel_btn = tk.Button(button_container,
                              text="Cancel",
                              command=self.destroy,
                              font=("Segoe UI", 12),
                              bg='#4a4a4a',
                              fg='#333333',
                              activebackground='#e0e0e0',
                              activeforeground='#333333',
                              relief='solid',
                              bd=1,
                              padx=25,
                              pady=8,
                              cursor='hand2')
        cancel_btn.pack(side="left", padx=(0, 20))
        
        # Status indicator
        status_label = tk.Label(button_container,
                               text="Ready to Launch",
                               font=("Segoe UI", 11),
                               bg='#eeeeee',
                               fg='#666666')
        status_label.pack(side="left", expand=True)
        
        # Launch button - primary action
        start_btn = tk.Button(button_container,
                             text="Launch Game",
                             command=self._start_game,
                             font=("Segoe UI", 12, "bold"),
                             bg='#0078d4',
                             fg='#ffffff',
                             activebackground='#106ebe',
                             activeforeground='#ffffff',
                             relief='flat',
                             bd=0,
                             padx=35,
                             pady=10,
                             cursor='hand2')
        start_btn.pack(side="right")
    
    def _on_nav_hover(self, frame, entering):
        """Simplified hover handler for navigation (no longer used with simple buttons)"""
        pass

    def _show_team_selection(self):
        """Show team selection section"""
        self._hide_all_sections()
        self.team_frame.pack(fill="both", expand=True)
        self._update_nav_buttons("SELECT TEAM")
        self.current_section = "SELECT TEAM"
    
    def _show_gm_profile(self):
        """Show GM profile section"""
        self._hide_all_sections()
        self.gm_frame.pack(fill="both", expand=True)
        self._update_nav_buttons("GM PROFILE")
        self.current_section = "GM PROFILE"
    
    def _show_game_settings(self):
        """Show game settings section"""
        self._hide_all_sections()
        self.settings_frame.pack(fill="both", expand=True)
        self._update_nav_buttons("GAME SETTINGS")
        self.current_section = "GAME SETTINGS"
    
    def _hide_all_sections(self):
        """Hide all content sections"""
        for frame in [self.team_frame, self.gm_frame, self.settings_frame]:
            frame.pack_forget()
    
    def _update_nav_buttons(self, active_section):
        """Update navigation button styles - temporarily simplified"""
        # Navigation cards are already styled and handle hover effects
        # Active state is shown through the content area switching
        pass
    
    def _create_footer(self, container):
        """Create sleek modern footer"""
        # Modern footer with dark theme
        footer_frame = tk.Frame(container, bg='#000000', height=60)
        footer_frame.pack(fill="x", side="bottom")
        footer_frame.pack_propagate(False)
        
        # Accent line at top
        accent_line = tk.Frame(footer_frame, height=2, bg='#00d4ff')
        accent_line.pack(fill="x", side="top")
        
        # Footer content
        footer_content = tk.Frame(footer_frame, bg='#000000')
        footer_content.pack(fill="both", expand=True, padx=40, pady=12)
        
        # Left - Version
        version_label = tk.Label(footer_content,
                                text="PUCK DYNASTY v1.0",
                                font=("Segoe UI", 10, "bold"),
                                bg='#000000',
                                fg='#00d4ff')
        version_label.pack(side="left", anchor="w")
        
        # Center - Status
        status_label = tk.Label(footer_content,
                               text="READY TO LAUNCH",
                               font=("Segoe UI", 10, "bold"),
                               bg='#000000',
                               fg='#ffffff')
        status_label.pack(expand=True)
        
        # Right - Copyright
        copyright_label = tk.Label(footer_content,
                                  text="© 2024 PUCK DYNASTY",
                                  font=("Segoe UI", 10),
                                  bg='#000000',
                                  fg='#666666')
        copyright_label.pack(side="right", anchor="e")
    
    def _create_team_selection(self):
        """Create clean, modern team selection interface"""
        # Clean main container
        main_container = tk.Frame(self.team_frame, bg='#3a3a3a')
        main_container.pack(fill="both", expand=True, padx=30, pady=20)
        
        # TITLE SECTION
        title_frame = tk.Frame(main_container, bg='#3a3a3a')
        title_frame.pack(fill="x", pady=(0, 20))
        
        title_label = tk.Label(title_frame, 
                              text="Select Your Team", 
                              font=("Segoe UI", 28, "bold"), 
                              bg='#3a3a3a', 
                              fg='#ffffff')
        title_label.pack(anchor='w')
        
        subtitle_label = tk.Label(title_frame, 
                                 text="Choose your NHL franchise and start your management career", 
                                 font=("Segoe UI", 14), 
                                 bg='#3a3a3a', 
                                 fg='#cccccc')
        subtitle_label.pack(anchor='w', pady=(5, 0))
        
        # Separator line
        separator = tk.Frame(title_frame, height=1, bg='#e0e0e0')
        separator.pack(fill="x", pady=(15, 0))
        
        # SEARCH SECTION
        search_frame = tk.Frame(main_container, bg='#3a3a3a')
        search_frame.pack(fill="x", pady=(0, 20))
        
        search_label = tk.Label(search_frame,
                               text="Search teams:",
                               font=("Segoe UI", 12, "bold"),
                               bg='#3a3a3a',
                               fg='#ffffff')
        search_label.pack(anchor='w', pady=(0, 5))
        
        # Modern search input - WHITE for text input
        search_input_frame = tk.Frame(search_frame, bg='#ffffff', relief='solid', bd=1)
        search_input_frame.pack(fill="x", ipady=5)
        
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_input_frame,
                               textvariable=self.search_var,
                               bg='#ffffff',
                               fg='#333333',
                               font=("Segoe UI", 12),
                               relief='flat',
                               bd=0,
                               insertbackground='#0078d4')
        search_entry.pack(fill="x", padx=8, pady=5)
        search_entry.bind('<KeyRelease>', self._filter_teams)
        
        # Placeholder text management
        def on_entry_click(event):
            if search_entry.get() == 'Search teams...':
                search_entry.delete(0, "end")
                search_entry.configure(fg='#333333')
        
        def on_focusout(event):
            if search_entry.get() == '':
                search_entry.insert(0, 'Search teams...')
                search_entry.configure(fg='#999999')
        
        search_entry.insert(0, 'Search teams...')
        search_entry.configure(fg='#999999')
        search_entry.bind('<FocusIn>', on_entry_click)
        search_entry.bind('<FocusOut>', on_focusout)
        
        # TEAMS GRID SECTION
        teams_label = tk.Label(main_container,
                              text="NHL Teams:",
                              font=("Segoe UI", 12, "bold"),
                              bg='#3a3a3a',
                              fg='#ffffff')
        teams_label.pack(anchor='w', pady=(10, 5))
        
        # Scrollable teams container
        teams_frame = tk.Frame(main_container, bg='#3a3a3a')
        teams_frame.pack(fill="both", expand=True)
        
        # Modern canvas with dark styling
        canvas = tk.Canvas(teams_frame, bg='#3a3a3a', highlightthickness=0, bd=0)
        
        # Clean scrollbar
        scrollbar = tk.Scrollbar(teams_frame, orient="vertical", command=canvas.yview,
                               bg='#d0d0d0', troughcolor='#e8e8e8',
                               activebackground='#0078d4',
                               width=14)
        
        self.teams_container = tk.Frame(canvas, bg='#3a3a3a', padx=10, pady=10)
        
        canvas.create_window((0, 0), window=self.teams_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.teams_container.bind("<Configure>", configure_scroll_region)
        
        # Team selection variable
        self.team_var = tk.StringVar()
        self.selected_team_card = None
        
        # Create modern team cards
        self._create_team_cards()
    
    def _create_team_cards(self):
        """Create clean, modern team selection cards"""
        # NHL team structure with full names
        nhl_structure = {
            "EASTERN CONFERENCE": {
                "Atlantic": {
                    "BOS": "Boston Bruins", "BUF": "Buffalo Sabres", "DET": "Detroit Red Wings", 
                    "FLA": "Florida Panthers", "MTL": "Montreal Canadiens", "OTT": "Ottawa Senators", 
                    "TB": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs"
                },
                "Metropolitan": {
                    "CAR": "Carolina Hurricanes", "CBJ": "Columbus Blue Jackets", "NJ": "New Jersey Devils", 
                    "NYI": "New York Islanders", "NYR": "New York Rangers", "PHI": "Philadelphia Flyers", 
                    "PIT": "Pittsburgh Penguins", "WSH": "Washington Capitals"
                }
            },
            "WESTERN CONFERENCE": {
                "Central": {
                    "ARI": "Arizona Coyotes", "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", 
                    "DAL": "Dallas Stars", "MIN": "Minnesota Wild", "NSH": "Nashville Predators", 
                    "STL": "St. Louis Blues", "WPG": "Winnipeg Jets"
                },
                "Pacific": {
                    "ANA": "Anaheim Ducks", "CGY": "Calgary Flames", "EDM": "Edmonton Oilers", 
                    "LA": "Los Angeles Kings", "SEA": "Seattle Kraken", "SJ": "San Jose Sharks", 
                    "VAN": "Vancouver Canucks", "VGS": "Vegas Golden Knights"
                }
            }
        }
        
        self.team_cards = []
        
        for conf_name, divisions in nhl_structure.items():
            # Clean conference header
            conf_header = tk.Label(self.teams_container,
                                  text=conf_name,
                                  font=("Segoe UI", 16, "bold"),
                                  bg='#3a3a3a',
                                  fg='#66B3FF')
            conf_header.pack(anchor='w', pady=(20, 10))
            
            for div_name, teams in divisions.items():
                # Simple division header
                div_label = tk.Label(self.teams_container,
                                    text=f"{div_name} Division",
                                    font=("Segoe UI", 14, "bold"),
                                    bg='#3a3a3a',
                                    fg='#cccccc')
                div_label.pack(anchor='w', pady=(15, 5))
                
                # Teams grid
                teams_grid_frame = tk.Frame(self.teams_container, bg='#3a3a3a')
                teams_grid_frame.pack(fill="x", pady=(0, 15))
                
                # Configure grid
                for c in range(2):
                    teams_grid_frame.grid_columnconfigure(c, weight=1, pad=10)
                
                # Create clean team cards
                for i, (team_code, team_name) in enumerate(teams.items()):
                    row = i // 2
                    col = i % 2
                    
                    # Modern team card with softer colors
                    card_frame = tk.Frame(teams_grid_frame,
                                        bg='#4a4a4a',
                                        relief='solid',
                                        bd=1,
                                        padx=15,
                                        pady=12)
                    card_frame.grid(row=row, column=col,
                                   sticky="ew",
                                   padx=5, pady=3)
                    
                    # Team info
                    team_code_label = tk.Label(card_frame,
                                              text=team_code,
                                              font=("Segoe UI", 11, "bold"),
                                              bg='#4a4a4a',
                                              fg='#0078d4')
                    team_code_label.pack(anchor='w')
                    
                    team_name_label = tk.Label(card_frame,
                                             text=team_name,
                                             font=("Segoe UI", 12),
                                             bg='#4a4a4a',
                                             fg='#333333')
                    team_name_label.pack(anchor='w', pady=(2, 0))
                    
                    # Store card reference
                    self.team_cards.append({
                        'code': team_code,
                        'name': team_name,
                        'frame': card_frame
                    })
                    
                    # Bind click events
                    for widget in [card_frame, team_code_label, team_name_label]:
                        widget.bind("<Button-1>", lambda e, code=team_code: self._select_team_card(code))
                        widget.bind("<Enter>", lambda e, frame=card_frame: self._on_team_hover(frame, True))
                        widget.bind("<Leave>", lambda e, frame=card_frame: self._on_team_hover(frame, False))
                        widget.configure(cursor="hand2")
                
        
        # Simple random team selection
        random_container = tk.Frame(self.teams_container, bg='#3a3a3a')
        random_container.pack(fill="x", pady=(20, 0))
        
        separator = tk.Frame(random_container, height=1, bg='#e0e0e0')
        separator.pack(fill="x", pady=(0, 15))
        
        random_btn = tk.Button(random_container,
                              text="🎲 Select Random Team",
                              command=self._select_random_team,
                              font=("Segoe UI", 12, "bold"),
                              bg='#28a745',
                              fg='#ffffff',
                              activebackground='#218838',
                              activeforeground='#ffffff',
                              relief='flat',
                              bd=0,
                              padx=20,
                              pady=10,
                              cursor='hand2')
        random_btn.pack(pady=10)
    
    def _on_team_hover(self, frame, entering):
        """Handle team card hover effects"""
        if entering:
            frame.configure(bg='#e8f4f8', relief='raised', bd=2)
        else:
            frame.configure(bg='#4a4a4a', relief='solid', bd=1)

    
    def _filter_teams(self, event=None):
        """Filter team cards based on search input"""
        search_text = self.search_var.get().lower()
        
        for card in self.team_cards:
            team_name = card['name'].lower()
            team_code = card['code'].lower()
            
            if search_text in team_name or search_text in team_code:
                # Show card by restoring its grid configuration
                parent = card['frame'].master
                info = card['frame'].grid_info()
                if info:  # Already gridded
                    pass
                else:
                    # Re-grid the card (this is simplified, real implementation would need proper positioning)
                    card['frame'].grid()
            else:
                # Hide card
                card['frame'].grid_remove()
    
    def _select_team_card(self, team_code):
        """Select a team card and update visual state with enhanced styling"""
        # Update selection variable
        self.team_var.set(team_code)
        self.selected_team_code = team_code
        
        # Update visual state of all cards
        for card in self.team_cards:
            if card['code'] == team_code:
                # SELECTED CARD - Dramatic highlight effect
                card['shadow'].configure(bg='#00ff88', padx=8, pady=8)
                card['border'].configure(bg='#00dd66')
                card['frame'].configure(bg='#004d2a')
                
                # Show selection indicator
                card['indicator'].pack(fill="x", pady=(10, 0))
                card['indicator'].configure(bg='#00ff88')
                
                # Update all child components for selected state
                for child in card['frame'].winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg='#004d2a')
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, tk.Label):
                                if grandchild.cget('bg') in ['#00d4ff', '#ffffff']:  # Badge
                                    grandchild.configure(bg='#ffffff', fg='#004d2a')
                                elif grandchild.cget('fg') == '#ffffff':  # Team name
                                    grandchild.configure(bg='#004d2a', fg='#ffffff')
                                else:  # Description
                                    grandchild.configure(bg='#004d2a', fg='#cccccc')
                    elif isinstance(child, tk.Label):
                        child.configure(bg='#004d2a')
                        
                self.selected_team_card = card['shadow']
                print(f"🏒 Selected team: {card['name']} ({team_code})")
            else:
                # UNSELECTED CARDS - Normal state
                card['shadow'].configure(bg='#000000', padx=4, pady=4)
                card['border'].configure(bg='#333333')
                card['frame'].configure(bg='#2a2a2a')
                
                # Hide selection indicator
                card['indicator'].pack_forget()
                
                # Restore normal appearance
                for child in card['frame'].winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg='#2a2a2a')
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, tk.Label):
                                if grandchild.cget('text') in [c['code'] for c in self.team_cards]:  # Badge
                                    grandchild.configure(bg='#00d4ff', fg='#000000')
                                elif grandchild.cget('fg') == '#ffffff':  # Team name
                                    grandchild.configure(bg='#2a2a2a', fg='#ffffff')
                                else:  # Description
                                    grandchild.configure(bg='#2a2a2a', fg='#888888')
                    elif isinstance(child, tk.Label):
                        child.configure(bg='#2a2a2a', fg='#888888')
    
    def _on_enhanced_card_hover(self, card_shadow, entering):
        """Enhanced hover effects for premium team cards"""
        # Find the card data
        card_data = None
        for card in self.team_cards:
            if card['shadow'] == card_shadow:
                card_data = card
                break
        
        if not card_data:
            return
            
        # Don't change appearance if this card is selected
        if hasattr(self, 'selected_team_card') and card_data['code'] == getattr(self, 'selected_team_code', None):
            return
        
        if entering:
            # Hover state - enhanced glow effect
            card_data['shadow'].configure(bg='#00d4ff', padx=6, pady=6)
            card_data['border'].configure(bg='#00b8e6')
            card_data['frame'].configure(bg='#003d4d')
            
            # Update all child widgets
            for child in card_data['frame'].winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg='#003d4d')
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tk.Label):
                            if grandchild.cget('bg') == '#00d4ff':  # Badge
                                grandchild.configure(bg='#ffffff', fg='#003d4d')
                            elif grandchild.cget('fg') == '#ffffff':  # Team name
                                grandchild.configure(bg='#003d4d', fg='#ffffff')
                            else:  # Description
                                grandchild.configure(bg='#003d4d', fg='#cccccc')
                elif isinstance(grandchild, tk.Label):
                    grandchild.configure(bg='#003d4d', fg='#cccccc')
        else:
            # Normal state - restore original colors
            card_data['shadow'].configure(bg='#000000', padx=4, pady=4)
            card_data['border'].configure(bg='#333333')
            card_data['frame'].configure(bg='#2a2a2a')
            
            # Restore child widgets
            for child in card_data['frame'].winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg='#2a2a2a')
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tk.Label):
                            if 'badge' in str(grandchild).lower() or grandchild.cget('bg') in ['#ffffff', '#00d4ff']:  # Badge
                                grandchild.configure(bg='#00d4ff', fg='#000000')
                            elif grandchild.cget('fg') == '#ffffff':  # Team name
                                grandchild.configure(bg='#2a2a2a', fg='#ffffff')
                            else:  # Description
                                grandchild.configure(bg='#2a2a2a', fg='#888888')
                elif isinstance(child, tk.Label):
                    child.configure(bg='#2a2a2a', fg='#888888')
    
    def _select_random_team(self):
        """Select a random team"""
        import random
        if self.team_cards:
            random_card = random.choice(self.team_cards)
            self._select_team_card(random_card['code'])


    
    def _create_game_settings(self):
        """Create modern game settings interface"""
        # Settings variables
        self.difficulty_var = tk.StringVar(value="Normal")
        self.season_length_var = tk.StringVar(value="Full Season (82 games)")
        self.database_size_var = tk.StringVar(value="Medium")
        self.financial_realism_var = tk.BooleanVar(value=True)
        self.injuries_var = tk.BooleanVar(value=True)
        self.fantasy_draft_var = tk.BooleanVar(value=False)
        self.salary_cap_var = tk.BooleanVar(value=True)
        
        # Main container with softer background
        main_container = tk.Frame(self.settings_frame, bg='#f5f5f5')
        main_container.pack(fill="both", expand=True, padx=40, pady=30)
        
        # Title section
        title_frame = tk.Frame(main_container, bg='#f5f5f5')
        title_frame.pack(fill="x", pady=(0, 30))
        
        title_label = tk.Label(title_frame, 
                              text="Game Settings",
                              font=("Segoe UI", 28, "bold"),
                              bg='#f5f5f5',
                              fg='#333333')
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(title_frame,
                                 text="Configure your hockey management experience",
                                 font=("Segoe UI", 14),
                                 bg='#f5f5f5',
                                 fg='#666666')
        subtitle_label.pack(anchor="w", pady=(5, 0))
        
        # Create scrollable content area
        canvas = tk.Canvas(main_container, bg='#f5f5f5', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f5f5f5')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_scroll_width)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create settings content
        self._create_modern_game_settings(scrollable_frame)
        
    def _create_modern_game_settings(self, parent):
        """Create modern game settings with clean cards"""
        # Database Size Section
        self._create_modern_settings_section(parent, "Database Size", 
            "Choose the scope of leagues and players in your game",
            [("Small", "Quick start: 8,000 players, essential leagues only"),
             ("Medium", "Balanced: 25,000 players, good depth (recommended)"),
             ("Large", "Extensive: 50,000 players, detailed minor leagues"),
             ("Massive", "Ultimate realism: 100,000+ players, global coverage")],
            self.database_size_var)
        
        # Difficulty Section
        self._create_modern_settings_section(parent, "Difficulty Level",
            "Adjust the challenge level for trades, contracts, and AI behavior",
            [("Rookie", "Easy mode with helpful hints and forgiving gameplay"),
             ("Normal", "Balanced challenge for most players"),
             ("Veteran", "Challenging gameplay for experienced managers"),
             ("Hall of Fame", "Ultimate challenge for hockey management masters")],
            self.difficulty_var)
        
        # Game Features Section
        self._create_modern_features_section(parent)
        
    def _create_modern_settings_section(self, parent, title, description, options, var):
        """Create a modern settings section with radio buttons"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text=title, 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        tk.Label(header_frame, text=description,
                font=("Segoe UI", 12), bg='#4a4a4a', fg='#cccccc',
                wraplength=500, justify="left").pack(anchor="w", pady=(5, 0))
        
        # Options content
        options_frame = tk.Frame(card_frame, bg='#4a4a4a')
        options_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        for value, desc in options:
            option_frame = tk.Frame(options_frame, bg='#4a4a4a', relief='solid', bd=1)
            option_frame.pack(fill="x", pady=(0, 8))
            
            # Radio button with option
            radio_frame = tk.Frame(option_frame, bg='#4a4a4a')
            radio_frame.pack(fill="x", padx=15, pady=10)
            
            radio = tk.Radiobutton(radio_frame, text=value, variable=var, value=value,
                                  font=("Segoe UI", 12, "bold"), bg='#4a4a4a', fg='#ffffff',
                                  activebackground='#fafafa', activeforeground='#333333',
                                  selectcolor='#fafafa')
            radio.pack(anchor="w")
            
            desc_label = tk.Label(radio_frame, text=desc,
                                 font=("Segoe UI", 10), bg='#4a4a4a', fg='#cccccc',
                                 wraplength=450, justify="left")
            desc_label.pack(anchor="w", padx=(20, 0), pady=(2, 0))
    
    def _create_modern_features_section(self, parent):
        """Create modern game features section with checkboxes"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Game Features", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        tk.Label(header_frame, text="Enable or disable specific game features",
                font=("Segoe UI", 12), bg='#4a4a4a', fg='#cccccc').pack(anchor="w", pady=(5, 0))
        
        # Features content
        features_frame = tk.Frame(card_frame, bg='#4a4a4a')
        features_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        # Feature options
        features = [
            ("Salary Cap Enforcement", self.salary_cap_var, "Enforce NHL salary cap rules and penalties"),
            ("Financial Realism", self.financial_realism_var, "Realistic team budgets and revenue management"),
            ("Player Injuries", self.injuries_var, "Enable realistic injury system affecting gameplay"),
            ("Fantasy Draft", self.fantasy_draft_var, "Redistribute all players through fantasy draft")
        ]
        
        for name, var, desc in features:
            feature_frame = tk.Frame(features_frame, bg='#4a4a4a', relief='solid', bd=1)
            feature_frame.pack(fill="x", pady=(0, 8))
            
            # Checkbox with feature
            check_frame = tk.Frame(feature_frame, bg='#4a4a4a')
            check_frame.pack(fill="x", padx=15, pady=10)
            
            checkbox = tk.Checkbutton(check_frame, text=name, variable=var,
                                     font=("Segoe UI", 12, "bold"), bg='#4a4a4a', fg='#ffffff',
                                     activebackground='#fafafa', activeforeground='#333333',
                                     selectcolor='#fafafa')
            checkbox.pack(anchor="w")
            
            desc_label = tk.Label(check_frame, text=desc,
                                 font=("Segoe UI", 10), bg='#4a4a4a', fg='#cccccc',
                                 wraplength=450, justify="left")
            desc_label.pack(anchor="w", padx=(20, 0), pady=(2, 0))
    
    def _create_gm_profile_tab(self):
        """Create modern GM profile tab with clean design"""
        # Main container with dark background
        main_container = tk.Frame(self.gm_frame, bg='#3a3a3a')
        main_container.pack(fill="both", expand=True, padx=40, pady=30)
        
        # Title section
        title_frame = tk.Frame(main_container, bg='#3a3a3a')
        title_frame.pack(fill="x", pady=(0, 30))
        
        title_label = tk.Label(title_frame, 
                              text="GM Profile",
                              font=("Segoe UI", 28, "bold"),
                              bg='#3a3a3a',
                              fg='#ffffff')
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(title_frame,
                                 text="Create your general manager identity and background",
                                 font=("Segoe UI", 14),
                                 bg='#f5f5f5',
                                 fg='#666666')
        subtitle_label.pack(anchor="w", pady=(5, 0))
        
        # Create scrollable content area
        canvas = tk.Canvas(main_container, bg='#f5f5f5', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f5f5f5')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def configure_scroll_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_scroll_width)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create the GM profile content
        self._create_gm_profile_section(scrollable_frame)
    

    

    
    def _create_gm_profile_section(self, parent):
        """Create comprehensive GM profile creation interface"""
        from game_classes import GMProfile
        
        # Initialize GM profile
        self.gm_profile = GMProfile()
        
        # Create form sections with modern cards
        self._create_modern_gm_personal_info(parent)
        self._create_modern_gm_background(parent)
        self._create_modern_gm_experience(parent)
        self._create_modern_gm_style(parent)
        self._create_modern_gm_generator(parent)
        
    def _create_modern_gm_personal_info(self, parent):
        """Create modern personal information section"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Personal Information", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Form content
        form_frame = tk.Frame(card_frame, bg='#4a4a4a')
        form_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Name entry
        self._create_modern_form_row(form_frame, "Full Name:", "gm_name_var", self.gm_profile.name)
        
        # Age selection
        age_frame = tk.Frame(form_frame, bg='#4a4a4a')
        age_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(age_frame, text="Age:", font=("Segoe UI", 12), 
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.age_var = tk.IntVar(value=self.gm_profile.age)
        age_spinbox = tk.Spinbox(age_frame, from_=25, to=70, width=10,
                                textvariable=self.age_var, font=("Segoe UI", 11),
                                bg='#4a4a4a', fg='#ffffff', relief='solid', bd=1,
                                buttonbackground='#e0e0e0', readonlybackground='#fafafa')
        age_spinbox.pack(anchor="w", pady=(5, 0))
        
        # Birthplace entry
        self._create_modern_form_row(form_frame, "Birthplace:", "birthplace_var", self.gm_profile.birthplace)
        
        # Nationality dropdown
        nat_frame = tk.Frame(form_frame, bg='#4a4a4a')
        nat_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(nat_frame, text="Nationality:", font=("Segoe UI", 12), 
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.nationality_var = tk.StringVar(value=self.gm_profile.nationality)
        nationality_dropdown = ttk.Combobox(nat_frame, textvariable=self.nationality_var,
                                           values=["Canadian", "American", "Swedish", "Finnish", 
                                                  "Russian", "Czech", "Slovak", "German", "Swiss", "Other"],
                                           state="readonly", font=("Segoe UI", 11))
        nationality_dropdown.pack(fill="x", pady=(5, 0))

    def _create_modern_gm_background(self, parent):
        """Create modern playing background section"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Playing Background", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Form content
        form_frame = tk.Frame(card_frame, bg='#4a4a4a')
        form_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Former player checkbox
        self.former_player_var = tk.BooleanVar(value=self.gm_profile.former_player)
        checkbox_frame = tk.Frame(form_frame, bg='#4a4a4a')
        checkbox_frame.pack(fill="x", pady=(0, 15))
        
        checkbox = tk.Checkbutton(checkbox_frame, text="Former Professional Player",
                                 variable=self.former_player_var, bg='#4a4a4a',
                                 font=("Segoe UI", 12), fg='#333333',
                                 activebackground='#f0f0f0', activeforeground='#333333')
        checkbox.pack(anchor="w")
        
        # NHL games played (if former player)
        career_frame = tk.Frame(form_frame, bg='#4a4a4a')
        career_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(career_frame, text="NHL Games Played:", font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.nhl_games_var = tk.IntVar(value=self.gm_profile.nhl_games_played)
        career_spinbox = tk.Spinbox(career_frame, from_=0, to=1500, width=10, increment=10,
                                   textvariable=self.nhl_games_var, font=("Segoe UI", 11),
                                   bg='#4a4a4a', fg='#ffffff', relief='solid', bd=1,
                                   buttonbackground='#e0e0e0', readonlybackground='#fafafa')
        career_spinbox.pack(anchor="w", pady=(5, 0))

    def _create_modern_gm_experience(self, parent):
        """Create modern management experience section"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Management Experience", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Form content
        form_frame = tk.Frame(card_frame, bg='#4a4a4a')
        form_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Years of coaching experience
        coaching_frame = tk.Frame(form_frame, bg='#4a4a4a')
        coaching_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(coaching_frame, text="Years of Coaching Experience:", font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.years_coaching_var = tk.IntVar(value=self.gm_profile.years_coaching)
        coaching_spinbox = tk.Spinbox(coaching_frame, from_=0, to=40, width=10,
                                     textvariable=self.years_coaching_var, font=("Segoe UI", 11),
                                     bg='#4a4a4a', fg='#ffffff', relief='solid', bd=1,
                                     buttonbackground='#e0e0e0', readonlybackground='#fafafa')
        coaching_spinbox.pack(anchor="w", pady=(5, 0))
        
        # Years as assistant GM
        assistant_frame = tk.Frame(form_frame, bg='#4a4a4a')
        assistant_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(assistant_frame, text="Years as Assistant GM:", font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.years_assistant_var = tk.IntVar(value=self.gm_profile.years_as_assistant)
        assistant_spinbox = tk.Spinbox(assistant_frame, from_=0, to=25, width=10,
                                      textvariable=self.years_assistant_var, font=("Segoe UI", 11),
                                      bg='#4a4a4a', fg='#ffffff', relief='solid', bd=1,
                                      buttonbackground='#e0e0e0', readonlybackground='#fafafa')
        assistant_spinbox.pack(anchor="w", pady=(5, 0))

    def _create_modern_gm_style(self, parent):
        """Create modern management style section"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Management Style", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Form content
        form_frame = tk.Frame(card_frame, bg='#4a4a4a')
        form_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Management style dropdown
        style_frame = tk.Frame(form_frame, bg='#4a4a4a')
        style_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(style_frame, text="Management Style:", font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.management_style_var = tk.StringVar(value=self.gm_profile.management_style)
        style_dropdown = ttk.Combobox(style_frame, textvariable=self.management_style_var,
                                     values=["Analytics-Based", "Traditional", "Player-First", "Balanced"],
                                     state="readonly", font=("Segoe UI", 11))
        style_dropdown.pack(fill="x", pady=(5, 0))
        
        # Risk tolerance dropdown
        risk_frame = tk.Frame(form_frame, bg='#4a4a4a')
        risk_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(risk_frame, text="Risk Tolerance:", font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        self.risk_tolerance_var = tk.StringVar(value=self.gm_profile.risk_tolerance)
        risk_dropdown = ttk.Combobox(risk_frame, textvariable=self.risk_tolerance_var,
                                    values=["Conservative", "Moderate", "Aggressive"],
                                    state="readonly", font=("Segoe UI", 11))
        risk_dropdown.pack(fill="x", pady=(5, 0))

    def _create_modern_gm_generator(self, parent):
        """Create modern random generator section"""
        # Section card
        card_frame = tk.Frame(parent, bg='#4a4a4a', relief='solid', bd=1)
        card_frame.pack(fill="x", pady=(0, 20), padx=0)
        
        # Header
        header_frame = tk.Frame(card_frame, bg='#4a4a4a')
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header_frame, text="Quick Setup", 
                font=("Segoe UI", 16, "bold"), bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Form content
        form_frame = tk.Frame(card_frame, bg='#4a4a4a')
        form_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Description
        desc_label = tk.Label(form_frame, 
                             text="Generate a random GM profile to get started quickly",
                             font=("Segoe UI", 12), bg='#4a4a4a', fg='#cccccc',
                             wraplength=400, justify="left")
        desc_label.pack(anchor="w", pady=(0, 15))
        
        # Random button
        random_btn = tk.Button(form_frame, text="🎲 Generate Random Profile",
                              command=self._generate_random_gm_profile,
                              font=("Segoe UI", 12, "bold"),
                              bg='#007acc', fg='#ffffff',
                              activebackground='#005a99', activeforeground='#ffffff',
                              relief='flat', bd=0, padx=20, pady=10,
                              cursor='hand2')
        random_btn.pack(anchor="w")
        
    def _generate_random_gm_profile(self):
        """Generate a random GM profile"""
        import random
        
        # Generate random name
        self._generate_random_gm_name()
        
        # Random age
        self.age_var.set(random.randint(30, 65))
        
        # Random birthplace
        cities = ["Toronto, ON", "Montreal, QC", "Boston, MA", "Detroit, MI", "Chicago, IL",
                 "New York, NY", "Philadelphia, PA", "Vancouver, BC", "Calgary, AB", "Edmonton, AB"]
        self.birthplace_var.set(random.choice(cities))
        
        # Random nationality
        nationalities = ["Canadian", "American", "Swedish", "Finnish", "Russian", "Czech"]
        self.nationality_var.set(random.choice(nationalities))
        
        # Random playing background
        self.former_player_var.set(random.choice([True, False]))
        self.nhl_games_var.set(random.randint(0, 800))
        
        # Random management experience  
        self.years_coaching_var.set(random.randint(0, 20))
        self.years_assistant_var.set(random.randint(0, 15))
        
        # Random style attributes
        self.management_style_var.set(random.choice(["Analytics-Based", "Traditional", "Player-First", "Balanced"]))
        self.risk_tolerance_var.set(random.choice(["Conservative", "Moderate", "Aggressive"]))

    def _create_modern_form_row(self, parent, label_text, var_name, default_value):
        """Create a modern form row with label and entry"""
        row_frame = tk.Frame(parent, bg='#4a4a4a')
        row_frame.pack(fill="x", pady=(0, 15))
        
        # Label
        tk.Label(row_frame, text=label_text, font=("Segoe UI", 12),
                bg='#4a4a4a', fg='#ffffff').pack(anchor="w")
        
        # Entry
        var = tk.StringVar(value=default_value)
        setattr(self, var_name, var)
        
        entry = tk.Entry(row_frame, textvariable=var, font=("Segoe UI", 11),
                        bg='#4a4a4a', fg='#ffffff', relief='solid', bd=1,
                        highlightthickness=1, highlightcolor='#007acc')
        entry.pack(fill="x", pady=(5, 0))
    
    def _generate_random_gm_name(self):
        """Generate a random GM name"""
        first_names = [
            "Alex", "Morgan", "Jordan", "Taylor", "Casey", "Riley", "Jamie", "Avery",
            "Blake", "Cameron", "Drew", "Hayden", "Parker", "Quinn", "Sage", "Rowan",
            "Michael", "David", "John", "Robert", "William", "James", "Christopher", "Daniel",
            "Matthew", "Anthony", "Mark", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
            "Sarah", "Emma", "Jessica", "Ashley", "Amanda", "Samantha", "Nicole", "Elizabeth",
            "Michelle", "Kimberly", "Amy", "Angela", "Tiffany", "Kayla", "Rebecca", "Rachel"
        ]
        
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
            "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
            "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
            "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
        ]
        
        import random
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        full_name = f"{first_name} {last_name}"
        
        if hasattr(self, 'gm_name_var'):
            self.gm_name_var.set(full_name)
            if hasattr(self, 'gm_name_entry'):
                self.gm_name_entry.config(fg='#ffffff')
                
    def _create_gm_personal_info_card(self, parent):
        """Create personal information section for GM profile"""
        card = self._create_profile_card(parent, "Personal Information", self.colors['accent_primary'])
        
        # Name
        self._create_gm_entry(card, "Full Name:", "gm_name_var", self.gm_profile.name)
        
        # Age
        self._create_gm_age_selector(card)
        
        # Birthplace and Nationality
        self._create_gm_entry(card, "Birthplace:", "birthplace_var", self.gm_profile.birthplace)
        
        # Nationality dropdown
        self._create_gm_dropdown(card, "Nationality:", "nationality_var", 
                                ["Canadian", "American", "Swedish", "Finnish", "Russian", "Czech", "Slovak", "German", "Swiss", "Other"],
                                self.gm_profile.nationality)
        
    def _create_gm_playing_background_card(self, parent):
        """Create playing background section for GM profile"""
        card = self._create_profile_card(parent, "Playing Background", '#4CAF50')
        
        # Former player checkbox
        self.former_player_var = tk.BooleanVar(value=self.gm_profile.former_player)
        checkbox_frame = tk.Frame(card, bg=self.colors['bg_tertiary'])
        checkbox_frame.pack(fill='x', pady=(0, 10))
        
        checkbox = tk.Checkbutton(checkbox_frame, text="Former Professional Player", 
                                 variable=self.former_player_var,
                                 font=("Segoe UI", 11, "bold"), fg=self.colors['text_primary'], bg=self.colors['bg_tertiary'],
                                 selectcolor=self.colors['bg_card'], activebackground=self.colors['bg_tertiary'],
                                 command=self._toggle_playing_fields)
        checkbox.pack(anchor='w')
        
        # Playing details frame (hidden by default)
        self.playing_details_frame = tk.Frame(card, bg=self.colors['bg_tertiary'])
        self.playing_details_frame.pack(fill='x', pady=(10, 0))
        
        # Position played
        self._create_gm_dropdown(self.playing_details_frame, "Primary Position:", "playing_position_var",
                                ["Center", "Left Wing", "Right Wing", "Defense", "Goaltender"],
                                self.gm_profile.playing_position)
        
        # NHL Games and Points
        self._create_gm_number_entry(self.playing_details_frame, "NHL Games Played:", "nhl_games_var", self.gm_profile.nhl_games_played)
        self._create_gm_number_entry(self.playing_details_frame, "Career Points:", "career_points_var", self.gm_profile.career_points)
        
        # Initially hide playing details
        if not self.gm_profile.former_player:
            self.playing_details_frame.pack_forget()
        
    def _create_gm_management_experience_card(self, parent):
        """Create management experience section for GM profile"""
        card = self._create_profile_card(parent, "Management Experience", '#FF9800')
        
        # Coaching experience
        self.coaching_exp_var = tk.BooleanVar(value=self.gm_profile.coaching_experience)
        coaching_checkbox = tk.Checkbutton(card, text="Coaching Experience", 
                                          variable=self.coaching_exp_var,
                                          font=("Segoe UI", 11, "bold"), fg=self.colors['text_primary'], bg=self.colors['bg_tertiary'],
                                          selectcolor=self.colors['bg_card'], activebackground=self.colors['bg_tertiary'],
                                          command=self._toggle_coaching_fields)
        coaching_checkbox.pack(anchor='w', pady=(0, 5))
        
        # Coaching years frame
        self.coaching_years_frame = tk.Frame(card, bg=self.colors['bg_tertiary'])
        self.coaching_years_frame.pack(fill='x', pady=(5, 10))
        self._create_gm_number_entry(self.coaching_years_frame, "Years Coaching:", "years_coaching_var", self.gm_profile.years_coaching)
        
        # Assistant GM experience
        self.assistant_gm_var = tk.BooleanVar(value=self.gm_profile.assistant_gm_experience)
        assistant_checkbox = tk.Checkbutton(card, text="Assistant GM Experience", 
                                           variable=self.assistant_gm_var,
                                           font=("Segoe UI", 11, "bold"), fg=self.colors['text_primary'], bg=self.colors['bg_tertiary'],
                                           selectcolor=self.colors['bg_card'], activebackground=self.colors['bg_tertiary'],
                                           command=self._toggle_assistant_fields)
        assistant_checkbox.pack(anchor='w', pady=(0, 5))
        
        # Assistant GM years frame
        self.assistant_years_frame = tk.Frame(card, bg=self.colors['bg_tertiary'])
        self.assistant_years_frame.pack(fill='x', pady=(5, 10))
        self._create_gm_number_entry(self.assistant_years_frame, "Years as Assistant:", "years_assistant_var", self.gm_profile.years_as_assistant)
        
        # Education
        self._create_gm_dropdown(card, "Education Level:", "education_var",
                                ["High School", "College", "University Degree", "MBA"],
                                self.gm_profile.education_level)
        
        # Initially hide experience fields if not selected
        if not self.gm_profile.coaching_experience:
            self.coaching_years_frame.pack_forget()
        if not self.gm_profile.assistant_gm_experience:
            self.assistant_years_frame.pack_forget()
            
    def _create_gm_style_traits_card(self, parent):
        """Create management style and personality traits section"""
        card = self._create_profile_card(parent, "Management Style & Traits", '#9C27B0')
        
        # Management Style
        self._create_gm_dropdown(card, "Management Style:", "management_style_var",
                                ["Analytics-Based", "Traditional", "Player-First", "Balanced"],
                                self.gm_profile.management_style)
        
        # Risk Tolerance
        self._create_gm_dropdown(card, "Risk Tolerance:", "risk_tolerance_var",
                                ["Conservative", "Moderate", "Aggressive"],
                                self.gm_profile.risk_tolerance)
        
        # Player Loyalty
        self._create_gm_dropdown(card, "Loyalty to Players:", "loyalty_var",
                                ["Low", "Medium", "High"],
                                self.gm_profile.loyalty_to_players)
        
        # Media Savvy
        self._create_gm_dropdown(card, "Media Relations:", "media_savvy_var",
                                ["Poor", "Average", "Good", "Excellent"],
                                self.gm_profile.media_savvy)
                                
    def _create_profile_card(self, parent, title, color):
        """Create a professional styled card for GM profile sections"""
        # Professional card container with shadow
        card_container = tk.Frame(parent, bg=self.colors['bg_card'])
        card_container.pack(fill='x', pady=(0, 20))
        
        # Shadow effect
        shadow_frame = tk.Frame(card_container, bg=self.colors['shadow'], height=1)
        shadow_frame.pack(fill='x', padx=(2, 0), pady=(0, 0))
        
        # Enhanced card with professional styling
        card = tk.Frame(card_container, bg=self.colors['bg_elevated'], relief='flat', bd=1, highlightbackground=self.colors['border'])
        card.pack(fill='x', padx=0, pady=(0, 2))
        
        # Professional header with gradient-style background
        header_frame = tk.Frame(card, bg=color, height=50)
        header_frame.pack(fill='x', side='top')
        header_frame.pack_propagate(False)
        
        # Enhanced header with icon and typography
        header = tk.Label(header_frame, text=f"● {title}", font=("Segoe UI", 14, "bold"),
                         bg=color, fg=self.colors['text_primary'])
        header.pack(expand=True, padx=25, pady=12)
        
        # Professional content area with better spacing
        content = tk.Frame(card, bg=self.colors['bg_elevated'])
        content.pack(fill='x', padx=25, pady=(15, 25))
        
        return content
        
    def _create_gm_entry(self, parent, label_text, var_name, default_value):
        """Create a text entry field for GM profile"""
        frame = tk.Frame(parent, bg=self.colors['bg_card'])
        frame.pack(fill='x', pady=(0, 10))
        
        label = tk.Label(frame, text=label_text, font=("Segoe UI", 11, "bold"),
                        bg=self.colors['bg_card'], fg=self.colors['text_primary'])
        label.pack(anchor='w', pady=(0, 5))
        
        var = tk.StringVar(value=default_value)
        setattr(self, var_name, var)
        
        entry = tk.Entry(frame, textvariable=var, font=("Segoe UI", 12),
                        bg=self.colors['bg_secondary'], fg=self.colors['text_primary'], relief='flat', bd=0,
                        insertbackground=self.colors['accent_primary'])
        entry.pack(fill='x', ipady=8)
        
        return var
        
    def _create_gm_dropdown(self, parent, label_text, var_name, options, default_value):
        """Create a dropdown for GM profile"""
        frame = tk.Frame(parent, bg=self.colors['bg_card'])
        frame.pack(fill='x', pady=(0, 10))
        
        label = tk.Label(frame, text=label_text, font=("Segoe UI", 11, "bold"),
                        bg=self.colors['bg_card'], fg=self.colors['text_primary'])
        label.pack(anchor='w', pady=(0, 5))
        
        var = tk.StringVar(value=default_value)
        setattr(self, var_name, var)
        
        combo = ttk.Combobox(frame, textvariable=var, values=options, 
                            state="readonly", font=("Segoe UI", 11))
        combo.pack(fill='x', ipady=4)
        
        return var
        
    def _create_gm_age_selector(self, parent):
        """Create age selector for GM profile"""
        frame = tk.Frame(parent, bg=self.colors['bg_card'])
        frame.pack(fill='x', pady=(0, 10))
        
        label = tk.Label(frame, text="Age:", font=("Segoe UI", 11, "bold"),
                        bg=self.colors['bg_card'], fg=self.colors['text_primary'])
        label.pack(anchor='w', pady=(0, 5))
        
        # Age spinbox
        self.age_var = tk.IntVar(value=self.gm_profile.age)
        age_spinbox = tk.Spinbox(frame, from_=25, to=70, textvariable=self.age_var,
                                font=("Segoe UI", 12), bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                                relief='flat', bd=0, insertbackground=self.colors['accent_primary'])
        age_spinbox.pack(fill='x', ipady=8)
        
    def _create_gm_number_entry(self, parent, label_text, var_name, default_value):
        """Create a number entry field for GM profile"""
        frame = tk.Frame(parent, bg=self.colors['bg_card'])
        frame.pack(fill='x', pady=(0, 10))
        
        label = tk.Label(frame, text=label_text, font=("Segoe UI", 11, "bold"),
                        bg=self.colors['bg_card'], fg=self.colors['text_primary'])
        label.pack(anchor='w', pady=(0, 5))
        
        var = tk.IntVar(value=default_value)
        setattr(self, var_name, var)
        
        entry = tk.Spinbox(frame, from_=0, to=2000, textvariable=var, 
                          font=("Segoe UI", 12), bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                          relief='flat', bd=0, insertbackground=self.colors['accent_primary'])
        entry.pack(fill='x', ipady=8)
        
        return var
        
    def _create_gm_random_generator(self, parent):
        """Create random profile generator section"""
        card = self._create_profile_card(parent, "Quick Setup", '#E91E63')
        
        desc = tk.Label(card, 
                       text="Generate a random GM profile if you want to jump straight into the game.",
                       bg=self.colors['bg_card'], fg=self.colors['text_secondary'], font=('Segoe UI', 10),
                       justify='left')
        desc.pack(anchor='w', pady=(0, 15))
        
        random_btn = tk.Button(card, text="🎲 Generate Random GM Profile", 
                              font=("Segoe UI", 12, "bold"),
                              bg='#E91E63', fg='white', relief='flat', bd=0,
                              cursor='hand2', pady=12,
                              command=self._generate_random_gm_profile)
        random_btn.pack(fill='x')
        
        # Button hover effects
        def on_enter_random(e):
            random_btn.configure(bg='#F06292')
        def on_leave_random(e):
            random_btn.configure(bg='#E91E63')
            
        random_btn.bind("<Enter>", on_enter_random)
        random_btn.bind("<Leave>", on_leave_random)
        
    def _toggle_playing_fields(self):
        """Toggle visibility of playing career fields"""
        if self.former_player_var.get():
            self.playing_details_frame.pack(fill='x', pady=(10, 0))
        else:
            self.playing_details_frame.pack_forget()
            
    def _toggle_coaching_fields(self):
        """Toggle visibility of coaching experience fields"""
        if self.coaching_exp_var.get():
            self.coaching_years_frame.pack(fill='x', pady=(5, 10))
        else:
            self.coaching_years_frame.pack_forget()
            
    def _toggle_assistant_fields(self):
        """Toggle visibility of assistant GM fields"""
        if self.assistant_gm_var.get():
            self.assistant_years_frame.pack(fill='x', pady=(5, 10))
        else:
            self.assistant_years_frame.pack_forget()
            
    def _generate_random_gm_profile(self):
        """Generate a completely random GM profile"""
        import random
        
        # Random personal info
        first_names = ["Alex", "Jordan", "Casey", "Taylor", "Sam", "Jamie", "Riley", "Cameron", "Morgan", "Avery", 
                      "Blake", "Drew", "Quinn", "Sage", "Rowan", "Finley", "Emerson", "Hayden", "Parker", "River"]
        last_names = ["Anderson", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                     "Hernandez", "Lopez", "Gonzalez", "Wilson", "Thompson", "Moore", "Taylor", "Jackson", "White", "Harris"]
        
        cities = ["Toronto, ON", "Montreal, QC", "Vancouver, BC", "Boston, MA", "New York, NY", "Detroit, MI", 
                 "Chicago, IL", "Philadelphia, PA", "Pittsburgh, PA", "Minneapolis, MN", "Edmonton, AB", "Calgary, AB"]
        
        nationalities = ["Canadian", "American", "Swedish", "Finnish", "Russian", "Czech", "Slovak", "German", "Swiss"]
        
        # Set random personal info
        self.gm_name_var.set(f"{random.choice(first_names)} {random.choice(last_names)}")
        self.age_var.set(random.randint(30, 60))
        self.birthplace_var.set(random.choice(cities))
        self.nationality_var.set(random.choice(nationalities))
        
        # Random playing background
        former_player = random.choice([True, False])
        self.former_player_var.set(former_player)
        
        if former_player:
            self.playing_position_var.set(random.choice(["Center", "Left Wing", "Right Wing", "Defense", "Goaltender"]))
            self.nhl_games_var.set(random.randint(0, 800))
            self.career_points_var.set(random.randint(0, 600))
            self._toggle_playing_fields()
        
        # Random management experience
        coaching_exp = random.choice([True, False])
        self.coaching_exp_var.set(coaching_exp)
        if coaching_exp:
            self.years_coaching_var.set(random.randint(1, 15))
            self._toggle_coaching_fields()
            
        assistant_exp = random.choice([True, False])
        self.assistant_gm_var.set(assistant_exp)
        if assistant_exp:
            self.years_assistant_var.set(random.randint(1, 10))
            self._toggle_assistant_fields()
            
        # Random education and traits
        self.education_var.set(random.choice(["High School", "College", "University Degree", "MBA"]))
        self.management_style_var.set(random.choice(["Analytics-Based", "Traditional", "Player-First", "Balanced"]))
        self.risk_tolerance_var.set(random.choice(["Conservative", "Moderate", "Aggressive"]))
        self.loyalty_var.set(random.choice(["Low", "Medium", "High"]))
        self.media_savvy_var.set(random.choice(["Poor", "Average", "Good", "Excellent"]))
    

    
    def _start_game(self):
        """Start the game with selected settings"""
        # Debug: Print current team selection
        current_team = self.team_var.get()
        print(f"DEBUG: Current team selection: '{current_team}'")
        
        # Validate team selection
        if not current_team:
            messagebox.showerror("No Team Selected", "Please select a team to manage.")
            return
        
        # Validate and collect GM profile
        from game_classes import GMProfile
        
        gm_name = self.gm_name_var.get().strip()
        if gm_name == "Your Name" or gm_name == "":
            gm_name = "General Manager"  # Default name
            
        # Create comprehensive GM profile
        gm_profile = GMProfile(
            name=gm_name,
            age=self.age_var.get(),
            birthplace=self.birthplace_var.get(),
            nationality=self.nationality_var.get(),
            former_player=self.former_player_var.get(),
            playing_position=self.playing_position_var.get(),
            nhl_games_played=self.nhl_games_var.get() if self.former_player_var.get() else 0,
            career_points=self.career_points_var.get() if self.former_player_var.get() else 0,
            coaching_experience=self.coaching_exp_var.get(),
            years_coaching=self.years_coaching_var.get() if self.coaching_exp_var.get() else 0,
            assistant_gm_experience=self.assistant_gm_var.get(),
            years_as_assistant=self.years_assistant_var.get() if self.assistant_gm_var.get() else 0,
            education_level=self.education_var.get(),
            management_style=self.management_style_var.get(),
            risk_tolerance=self.risk_tolerance_var.get(),
            loyalty_to_players=self.loyalty_var.get(),
            media_savvy=self.media_savvy_var.get()
        )
        
        # Collect all settings (non-negotiables are hardcoded)
        self.game_settings = {
            'selected_team': self.team_var.get(),
            'gm_name': gm_name,
            'gm_profile': gm_profile,
            'difficulty': self.difficulty_var.get(),
            'season_length': self.season_length_var.get(),
            'database_size': self.database_size_var.get(),
            'financial_realism': self.financial_realism_var.get(),
            'salary_cap': self.salary_cap_var.get(),
            'injuries_enabled': self.injuries_var.get(),
            'fantasy_draft': self.fantasy_draft_var.get(),
            
            # Non-negotiable options (always enabled)
            'trades_enabled': True,
            'draft_enabled': True,
            'playoffs': True,
            'season_start': "Regular Season Start",
            'season_games': "82 games",
            'rookie_development': "Realistic",
            'trade_difficulty': "Realistic",
            'morale_system': True,
            'player_personalities': True,
            'media_pressure': True,
            'media_engagement': 'Standard'
        }
        
        self.selected_team = self.team_var.get()
        
        # Clean up image references before closing
        self._cleanup_resources()
        
        # Close the startup window
        self.destroy()
    
    def _cleanup_resources(self):
        """Clean up image resources to prevent memory leaks"""
        try:
            if hasattr(self, 'background_photo') and self.background_photo:
                # Properly delete the PhotoImage
                del self.background_photo
                self.background_photo = None
            if hasattr(self, 'background_image') and self.background_image:
                self.background_image.close()
                del self.background_image
                self.background_image = None
            if hasattr(self, 'bg_image_id'):
                del self.bg_image_id
        except Exception as e:
            print(f"Error cleaning up resources: {e}")
    
    def _on_closing(self):
        """Handle window closing properly"""
        self._cleanup_resources()
        self.destroy()
    
    def destroy(self):
        """Override destroy to ensure proper cleanup"""
        self._cleanup_resources()
        super().destroy()

# Test function for the startup window
def test_startup_window():
    """Test the startup window"""
    app = StartupWindow()
    app.mainloop()
    
    if app.game_settings:
        print("Game Settings Selected:")
        for key, value in app.game_settings.items():
            print(f"  {key}: {value}")
        return app.game_settings
    else:
        print("Game cancelled")
        return None

if __name__ == "__main__":
    test_startup_window()
