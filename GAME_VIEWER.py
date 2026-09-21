"""
REBUILT NHL GAME VIEWER FROM SCRATCH
Professional hockey game viewer with proper coordinate mapping and PNG background
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import math
import time
import os
from typing import Dict, List, Tuple, Optional, Any
import threading
import json

class RebuiltNHLGameViewer:
    """
    Completely rebuilt NHL Game Viewer with:
    - Proper PNG background loading and scaling
    - Accurate coordinate mapping
    - Realistic rink boundaries
    - Professional player animations
    - Event-driven game simulation
    """
    
    def __init__(self, root=None, event_log=None, duration=3600, home_team="HOME", away_team="AWAY"):
        # Window setup
        if root is None:
            self.root = tk.Tk()
            self.owns_root = True
        else:
            self.root = root
            self.owns_root = False
            
        self.setup_window()
        
        # Game data
        self.event_log = event_log or []
        self.duration = duration
        self.home_team = home_team
        self.away_team = away_team
        
        # Rink and canvas properties - CORRECTED SIZING
        self.canvas_width = 800     # Compact canvas for rink display
        self.canvas_height = 400    # Appropriate height for compact view
        self.rink_image = None
        self.rink_photo = None
        self.rink_display_width = 700   # Display width for rink (smaller than canvas)
        self.rink_display_height = 350  # Display height for rink
        
        # Coordinate mapping - NHL rink is 200ft x 85ft
        self.rink_length_ft = 200    # NHL standard length
        self.rink_width_ft = 85      # NHL standard width
        
        # Rink margins and positioning
        self.rink_margin_x = 50     # Left margin for rink positioning
        self.rink_margin_y = 25     # Top margin for rink positioning
        
        # Initialize coordinate mapping attributes to prevent AttributeError
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
        # Rink boundaries (will be calculated after image load)
        self.rink_bounds = {
            'left': 0,
            'right': 0,
            'top': 0, 
            'bottom': 0,
            'center_x': 0,
            'center_y': 0
        }
        
        # Player and game objects
        self.home_players = {}       # Canvas objects for home players
        self.away_players = {}       # Canvas objects for away players
        self.puck = None            # Canvas object for puck
        self.player_data = {}       # Player position and info data
        self.puck_data = {'x': 0, 'y': 0}  # Puck position data
        
        # Animation and playback - ENHANCED FOR FLUID MOVEMENT
        self.current_time = 0.0
        self.is_playing = False
        self.playback_speed = 1.0
        self.event_index = 0
        self.animation_running = False
        
        # Enhanced animation system for fluid movement
        self.active_animations = {}  # Track ongoing animations
        self.animation_frame_rate = 60  # 60 FPS for smooth movement
        self.animation_frame_time = 1000 // self.animation_frame_rate  # ~16ms per frame
        
        # Colors and styling
        self.colors = {
            'home_player': '#0066CC',      # Blue
            'away_player': '#CC0000',      # Red
            'home_goalie': '#003399',      # Dark blue
            'away_goalie': '#990000',      # Dark red
            'puck': '#333333',             # Dark gray
            'ice': '#F0F8FF',              # Ice blue
            'board': '#8B4513',            # Brown
            'line': '#FF0000'              # Red lines
        }
        
        # Initialize interface
        self.create_interface()
        self.load_rink_background()
        # Note: setup_rink_coordinate_mapping() is called within load_rink_background()
        self.initialize_game_objects()
        
        print("🏒 Rebuilt NHL Game Viewer initialized successfully!")
        
    def setup_window(self):
        """Configure the main window with proper layout"""
        self.root.title("🏒 NHL Game Viewer - Professional Edition (PERFECTED)")
        self.root.geometry("1200x800")  # Overall window size
        self.root.configure(bg='#0f1419')  # Dark theme
        self.root.resizable(True, True)
        
    def create_interface(self):
        """Create the main interface with compact rink and side panels"""
        # Main container with padding
        self.main_frame = tk.Frame(self.root, bg='#0f1419')
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header with team info and controls
        self.create_header()
        
        # Content area with rink and side panels
        content_frame = tk.Frame(self.main_frame, bg='#0f1419')
        content_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Left panel for stats
        self.create_left_panel(content_frame)
        
        # Center area for game canvas
        self.create_game_canvas(content_frame)
        
        # Right panel for controls and info
        self.create_right_panel(content_frame)
        
        # Bottom controls
        self.create_controls()
        
        # Status bar
        self.create_status_bar()
    
    def create_left_panel(self, parent):
        """Create left panel with game statistics"""
        left_panel = tk.Frame(parent, bg='#1a2332', width=200)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Panel title
        title = tk.Label(left_panel, text="GAME STATS", 
                        font=('Segoe UI', 12, 'bold'), 
                        fg='#ffffff', bg='#1a2332')
        title.pack(pady=10)
        
        # Score display
        self.score_frame = tk.Frame(left_panel, bg='#1a2332')
        self.score_frame.pack(fill='x', padx=10, pady=5)
        
        self.home_score_label = tk.Label(self.score_frame, text="HOME: 0", 
                                        font=('Segoe UI', 10, 'bold'), 
                                        fg='#4caf50', bg='#1a2332')
        self.home_score_label.pack()
        
        self.away_score_label = tk.Label(self.score_frame, text="AWAY: 0", 
                                        font=('Segoe UI', 10, 'bold'), 
                                        fg='#f44336', bg='#1a2332')
        self.away_score_label.pack()
        
        # Game events log
        events_label = tk.Label(left_panel, text="RECENT EVENTS", 
                               font=('Segoe UI', 10, 'bold'), 
                               fg='#ffffff', bg='#1a2332')
        events_label.pack(pady=(20, 5))
        
        self.events_text = tk.Text(left_panel, height=10, width=25,
                                  font=('Segoe UI', 8),
                                  bg='#2a2a2a', fg='#ffffff',
                                  wrap='word', state='disabled')
        self.events_text.pack(padx=10, pady=(0, 10))
    
    def create_right_panel(self, parent):
        """Create right panel with controls and player info"""
        right_panel = tk.Frame(parent, bg='#1a2332', width=200)
        right_panel.pack(side='right', fill='y', padx=(10, 0))
        right_panel.pack_propagate(False)
        
        # Panel title
        title = tk.Label(right_panel, text="PLAYER INFO", 
                        font=('Segoe UI', 12, 'bold'), 
                        fg='#ffffff', bg='#1a2332')
        title.pack(pady=10)
        
        # Player details
        self.player_info_frame = tk.Frame(right_panel, bg='#1a2332')
        self.player_info_frame.pack(fill='x', padx=10, pady=5)
        
        # Game controls
        controls_label = tk.Label(right_panel, text="GAME CONTROLS", 
                                 font=('Segoe UI', 10, 'bold'), 
                                 fg='#ffffff', bg='#1a2332')
        controls_label.pack(pady=(20, 5))
        
        # Camera controls
        camera_frame = tk.Frame(right_panel, bg='#1a2332')
        camera_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(camera_frame, text="🏠 Home Zone", 
                 font=('Segoe UI', 8), bg='#4caf50', fg='white',
                 command=self.focus_home_zone).pack(fill='x', pady=2)
        
        tk.Button(camera_frame, text="🎯 Center Ice", 
                 font=('Segoe UI', 8), bg='#ff9800', fg='white',
                 command=self.focus_center_ice).pack(fill='x', pady=2)
        
        tk.Button(camera_frame, text="🥅 Away Zone", 
                 font=('Segoe UI', 8), bg='#f44336', fg='white',
                 command=self.focus_away_zone).pack(fill='x', pady=2)
        
    def create_header(self):
        """Create header with team information"""
        header_frame = tk.Frame(self.main_frame, bg='#1a2332', height=80)
        header_frame.pack(fill='x', pady=(0, 10))
        header_frame.pack_propagate(False)
        
        # Team vs Team display
        team_frame = tk.Frame(header_frame, bg='#1a2332')
        team_frame.pack(expand=True)
        
        # Home team
        home_label = tk.Label(team_frame, text=self.home_team, 
                             font=('Segoe UI', 18, 'bold'), 
                             fg='#ffffff', bg='#1a2332')
        home_label.pack(side='left', padx=20, pady=20)
        
        # VS
        vs_label = tk.Label(team_frame, text="VS", 
                           font=('Segoe UI', 14, 'bold'), 
                           fg='#cccccc', bg='#1a2332')
        vs_label.pack(side='left', padx=20, pady=20)
        
        # Away team
        away_label = tk.Label(team_frame, text=self.away_team, 
                             font=('Segoe UI', 18, 'bold'), 
                             fg='#ffffff', bg='#1a2332')
        away_label.pack(side='left', padx=20, pady=20)
        
        # Game time display
        self.time_label = tk.Label(team_frame, text="00:00 - 1st Period", 
                                  font=('Segoe UI', 14), 
                                  fg='#ffeb3b', bg='#1a2332')
        self.time_label.pack(side='right', padx=20, pady=20)
        
    def create_game_canvas(self, parent):
        """Create the compact game display canvas"""
        canvas_frame = tk.Frame(parent, bg='#0f1419')
        canvas_frame.pack(side='left', fill='both', expand=True, padx=(0, 0))
        
        # Compact canvas for rink display
        self.canvas = tk.Canvas(canvas_frame, 
                               width=self.canvas_width, 
                               height=self.canvas_height,
                               bg='#0f1419', 
                               highlightthickness=1,
                               highlightbackground='#333333')
        self.canvas.pack(expand=True)
        
        # Bind mouse events for interaction
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_hover)
        
    def create_controls(self):
        """Create playback controls"""
        controls_frame = tk.Frame(self.main_frame, bg='#1a2332', height=60)
        controls_frame.pack(fill='x', pady=(0, 10))
        controls_frame.pack_propagate(False)
        
        # Playback buttons
        button_frame = tk.Frame(controls_frame, bg='#1a2332')
        button_frame.pack(side='left', padx=20, pady=10)
        
        self.play_button = tk.Button(button_frame, text="▶ Play", 
                                    command=self.toggle_playback,
                                    font=('Segoe UI', 10, 'bold'),
                                    bg='#4caf50', fg='white',
                                    relief='flat', padx=15)
        self.play_button.pack(side='left', padx=5)
        
        self.pause_button = tk.Button(button_frame, text="⏸ Pause", 
                                     command=self.pause_playback,
                                     font=('Segoe UI', 10, 'bold'),
                                     bg='#ff9800', fg='white',
                                     relief='flat', padx=15)
        self.pause_button.pack(side='left', padx=5)
        
        self.reset_button = tk.Button(button_frame, text="⏹ Reset", 
                                     command=self.reset_playback,
                                     font=('Segoe UI', 10, 'bold'),
                                     bg='#f44336', fg='white',
                                     relief='flat', padx=15)
        self.reset_button.pack(side='left', padx=5)
        
        # Speed control
        speed_frame = tk.Frame(controls_frame, bg='#1a2332')
        speed_frame.pack(side='right', padx=20, pady=10)
        
        tk.Label(speed_frame, text="Speed:", 
                font=('Segoe UI', 10), fg='white', bg='#1a2332').pack(side='left')
        
        self.speed_var = tk.StringVar(value="1.0x")
        speed_menu = ttk.Combobox(speed_frame, textvariable=self.speed_var,
                                 values=["0.5x", "1.0x", "1.5x", "2.0x", "3.0x"],
                                 state="readonly", width=8)
        speed_menu.pack(side='left', padx=5)
        speed_menu.bind('<<ComboboxSelected>>', self.on_speed_change)
        
    def create_status_bar(self):
        """Create status bar for debugging and info"""
        self.status_label = tk.Label(self.main_frame, text="Ready", 
                                    font=('Segoe UI', 9), 
                                    fg='#cccccc', bg='#0f1419',
                                    anchor='w')
        self.status_label.pack(fill='x', pady=(5, 0))
        
    def load_rink_background(self):
        """Load the PUCKDYNASTYRINKCOMPLETE.png background and setup coordinate mapping"""
        try:
            rink_path = "PUCKDYNASTYRINKCOMPLETE.png"
            
            if os.path.exists(rink_path):
                # Load the existing rink image
                image = Image.open(rink_path)
                
                # Get original image dimensions
                original_width = image.width
                original_height = image.height
                
                # Calculate optimal size to fit canvas while maintaining aspect ratio
                img_ratio = original_width / original_height
                canvas_ratio = self.canvas_width / self.canvas_height
                
                if img_ratio > canvas_ratio:
                    # Image is wider - fit to canvas width
                    self.rink_display_width = int(self.canvas_width * 0.95)  # 95% of canvas
                    self.rink_display_height = int(self.rink_display_width / img_ratio)
                else:
                    # Image is taller - fit to canvas height  
                    self.rink_display_height = int(self.canvas_height * 0.95)  # 95% of canvas
                    self.rink_display_width = int(self.rink_display_height * img_ratio)
                
                # Resize the image to fit display
                self.rink_image = image.resize((self.rink_display_width, self.rink_display_height), Image.Resampling.LANCZOS)
                self.rink_photo = ImageTk.PhotoImage(self.rink_image)
                
                # Set up coordinate system based on loaded rink
                self.setup_rink_coordinate_mapping()
                
                print(f"✅ Loaded PUCKDYNASTYRINKCOMPLETE.png ({self.rink_display_width}x{self.rink_display_height})")
                self.status_label.config(text=f"✅ Rink loaded: {self.rink_display_width}x{self.rink_display_height}")
                
            else:
                print(f"❌ PUCKDYNASTYRINKCOMPLETE.png not found")
                self.create_fallback_rink()
                self.status_label.config(text="⚠️ Using fallback rink - PNG not found")
                
        except Exception as e:
            print(f"Error loading rink background: {e}")
            self.create_fallback_rink()
            self.status_label.config(text="⚠️ Using fallback rink - Error loading PNG")
    
    def create_fallback_rink(self):
        """Create a simple fallback rink if PNG not available"""
        # Create a basic rink image with proper dimensions
        fallback_image = Image.new('RGB', (self.rink_display_width, self.rink_display_height), '#F0F8FF')  # Ice blue
        self.rink_image = fallback_image
        self.rink_photo = ImageTk.PhotoImage(self.rink_image)
        
    def setup_coordinate_system(self):
        """Setup the coordinate mapping system based on compact rink display"""
        if not self.rink_image:
            print("No rink image loaded for coordinate setup")
            return
            
        # Position rink with margins for a compact display
        rink_left = self.rink_margin_x
        rink_top = self.rink_margin_y
        
        # Set rink boundaries based on display dimensions
        self.rink_bounds = {
            'left': rink_left,
            'right': rink_left + self.rink_display_width,
            'top': rink_top,
            'bottom': rink_top + self.rink_display_height,
            'center_x': rink_left + (self.rink_display_width // 2),
            'center_y': rink_top + (self.rink_display_height // 2)
        }
        
        # Calculate scaling factors for game coordinates
        # Add padding to keep players clearly visible within rink
        padding_ratio = 0.85  # Use 85% of rink for player movement
        usable_width = self.rink_display_width * padding_ratio
        usable_height = self.rink_display_height * padding_ratio
        
        self.scale_x = usable_width / self.rink_length_ft   # pixels per foot
        self.scale_y = usable_height / self.rink_width_ft   # pixels per foot
        
        # Offset for centering the usable area
        self.offset_x = (self.rink_display_width - usable_width) / 2
        self.offset_y = (self.rink_display_height - usable_height) / 2
        
        print(f"🏒 CORRECTED Coordinate system setup:")
        print(f"   Rink bounds: {self.rink_bounds}")
        print(f"   Scale: {self.scale_x:.2f} x {self.scale_y:.2f} pixels/foot")
        print(f"   Padding: {padding_ratio*100}% usable area")
        print(f"   Offsets: {self.offset_x:.1f}, {self.offset_y:.1f}")
        
    def game_to_canvas_coords(self, game_x: float, game_y: float) -> Tuple[int, int]:
        """
        Convert game coordinates to canvas pixel coordinates with proper padding
        Game coordinates: (0,0) = bottom-left corner, (200,85) = top-right corner in feet
        Canvas coordinates: (0,0) = top-left, with rink positioned using margins and offsets
        """
        # Convert game coordinates (feet) to canvas coordinates (pixels)
        canvas_x = self.rink_bounds['left'] + self.offset_x + (game_x * self.scale_x)
        canvas_y = self.rink_bounds['top'] + self.offset_y + ((self.rink_width_ft - game_y) * self.scale_y)  # Flip Y axis
        
        return int(canvas_x), int(canvas_y)
    
    def canvas_to_game_coords(self, canvas_x: int, canvas_y: int) -> Tuple[float, float]:
        """Convert canvas pixel coordinates back to game coordinates"""
        game_x = (canvas_x - self.rink_bounds['left'] - self.offset_x) / self.scale_x
        game_y = self.rink_width_ft - ((canvas_y - self.rink_bounds['top'] - self.offset_y) / self.scale_y)
        
        return game_x, game_y
    
    def initialize_game_objects(self):
        """Initialize players and puck on the canvas"""
        # Place rink background first
        try:
            if self.rink_photo and self.rink_photo.width() > 0:
                self.canvas.create_image(
                    self.rink_bounds['center_x'], 
                    self.rink_bounds['center_y'],
                    image=self.rink_photo,
                    tags="rink"
                )
                print("✅ PUCKDYNASTYRINKCOMPLETE.png successfully placed on canvas")
            else:
                print("❌ PNG failed to load - using fallback rink")
                self.create_simple_rink_outline()
        except Exception as e:
            print(f"❌ Exception placing PNG on canvas: {e}")
            self.create_simple_rink_outline()
        
        # Initialize player positions (standard hockey formation)
        self.setup_initial_positions()
        
        # Create player objects
        self.create_player_objects()
        
    def create_simple_rink_outline(self):
        """Create a simple rink outline if image loading fails"""
        print("🚨 WARNING: Using fallback rink outline instead of PNG!")
        
        # Draw rink outline
        self.canvas.create_rectangle(
            self.rink_bounds['left'], 
            self.rink_bounds['top'],
            self.rink_bounds['right'], 
            self.rink_bounds['bottom'],
            outline='blue', 
            width=2, 
            fill='lightblue',
            tags="rink"
        )
        
        # Draw center line
        center_x = self.rink_bounds['center_x']
        self.canvas.create_line(
            center_x, self.rink_bounds['top'],
            center_x, self.rink_bounds['bottom'],
            fill='red', width=2, tags="rink"
        )
        
        # Create puck
        self.create_puck_object()
        
    def setup_initial_positions(self):
        """Set up initial player positions for face-off with CORRECTED coordinates"""
        center_x, center_y = 100, 42.5  # Center ice in feet
        
        # Home team (left side) - CORRECTED positions in feet
        home_positions = [
            # Forwards
            (90, 42.5),   # Center
            (85, 35),     # Left wing  
            (85, 50),     # Right wing
            # Defense
            (60, 25),     # Left defense (moved inward)
            (60, 60),     # Right defense (moved inward)
            # Goalie - CORRECTED to be inside rink
            (25, 42.5)    # Home goalie (moved significantly inward)
        ]
        
        # Away team (right side) - CORRECTED positions in feet  
        away_positions = [
            # Forwards
            (110, 42.5),  # Center
            (115, 50),    # Left wing (flipped)
            (115, 35),    # Right wing (flipped)
            # Defense
            (140, 60),    # Left defense (moved inward)
            (140, 25),    # Right defense (moved inward)
            # Goalie - CORRECTED to be inside rink
            (175, 42.5)   # Away goalie (moved significantly inward)
        ]
        
        # Store positions
        self.player_data = {
            'home': [{'x': x, 'y': y, 'id': f'home_{i}'} for i, (x, y) in enumerate(home_positions)],
            'away': [{'x': x, 'y': y, 'id': f'away_{i}'} for i, (x, y) in enumerate(away_positions)]
        }
        
        # Puck at center
        self.puck_data = {'x': center_x, 'y': center_y}
        
        print(f"🏒 CORRECTED Player positions:")
        print(f"   Home goalie: ({home_positions[5][0]}, {home_positions[5][1]})")
        print(f"   Away goalie: ({away_positions[5][0]}, {away_positions[5][1]})")
        print(f"   Center ice: ({center_x}, {center_y})")
        
    def create_player_objects(self):
        """Create visual player objects on canvas"""
        player_radius = 8
        
        # Create home players
        for i, player in enumerate(self.player_data['home']):
            canvas_x, canvas_y = self.game_to_canvas_coords(player['x'], player['y'])
            
            # Determine if goalie (last player)
            is_goalie = (i == len(self.player_data['home']) - 1)
            color = self.colors['home_goalie'] if is_goalie else self.colors['home_player']
            
            player_obj = self.canvas.create_oval(
                canvas_x - player_radius, canvas_y - player_radius,
                canvas_x + player_radius, canvas_y + player_radius,
                fill=color, outline='white', width=2,
                tags=f"player home {player['id']}"
            )
            
            # Add player number
            self.canvas.create_text(
                canvas_x, canvas_y,
                text=str(i + 1), fill='white',
                font=('Arial', 8, 'bold'),
                tags=f"number home {player['id']}"
            )
            
            self.home_players[player['id']] = player_obj
            
        # Create away players
        for i, player in enumerate(self.player_data['away']):
            canvas_x, canvas_y = self.game_to_canvas_coords(player['x'], player['y'])
            
            # Determine if goalie (last player)
            is_goalie = (i == len(self.player_data['away']) - 1)
            color = self.colors['away_goalie'] if is_goalie else self.colors['away_player']
            
            player_obj = self.canvas.create_oval(
                canvas_x - player_radius, canvas_y - player_radius,
                canvas_x + player_radius, canvas_y + player_radius,
                fill=color, outline='white', width=2,
                tags=f"player away {player['id']}"
            )
            
            # Add player number
            self.canvas.create_text(
                canvas_x, canvas_y,
                text=str(i + 1), fill='white',
                font=('Arial', 8, 'bold'),
                tags=f"number away {player['id']}"
            )
            
            self.away_players[player['id']] = player_obj
    
    def create_puck_object(self):
        """Create puck object on canvas"""
        puck_radius = 4
        canvas_x, canvas_y = self.game_to_canvas_coords(self.puck_data['x'], self.puck_data['y'])
        
        self.puck = self.canvas.create_oval(
            canvas_x - puck_radius, canvas_y - puck_radius,
            canvas_x + puck_radius, canvas_y + puck_radius,
            fill=self.colors['puck'], outline='white', width=2,
            tags="puck"
        )
    
    def update_player_position(self, team: str, player_id: str, x: float, y: float):
        """Update a player's position on the canvas"""
        canvas_x, canvas_y = self.game_to_canvas_coords(x, y)
        
        # Update player object
        players_dict = self.home_players if team == 'home' else self.away_players
        if player_id in players_dict:
            player_obj = players_dict[player_id]
            self.canvas.coords(player_obj, 
                             canvas_x - 8, canvas_y - 8,
                             canvas_x + 8, canvas_y + 8)
            
            # Update number text
            number_objs = self.canvas.find_withtag(f"number {team} {player_id}")
            for obj in number_objs:
                self.canvas.coords(obj, canvas_x, canvas_y)
    
    def update_puck_position(self, x: float, y: float):
        """Update puck position on the canvas"""
        canvas_x, canvas_y = self.game_to_canvas_coords(x, y)
        
        if self.puck:
            self.canvas.coords(self.puck,
                             canvas_x - 4, canvas_y - 4,
                             canvas_x + 4, canvas_y + 4)
    
    def toggle_playback(self):
        """Toggle between play and pause"""
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        """Start game playback"""
        self.is_playing = True
        self.play_button.config(text="⏸ Pause")
        
        if not self.animation_running:
            self.animation_running = True
            self.animate_game()
    
    def pause_playback(self):
        """Pause game playback"""
        self.is_playing = False
        self.play_button.config(text="▶ Play")
    
    def reset_playback(self):
        """Reset game to beginning and cancel all animations"""
        self.is_playing = False
        self.current_time = 0.0
        self.event_index = 0
        self.play_button.config(text="▶ Play")
        
        # Cancel all active animations for smooth reset
        self.cancel_all_animations()
        
        # Reset positions
        self.setup_initial_positions()
        self.update_all_positions()
    
    def cancel_all_animations(self):
        """Cancel all active animations"""
        for animation_key, animation_data in self.active_animations.items():
            if 'after_id' in animation_data and animation_data['after_id']:
                self.root.after_cancel(animation_data['after_id'])
        
        self.active_animations.clear()
    
    def on_speed_change(self, event=None):
        """Handle speed change"""
        speed_text = self.speed_var.get()
        self.playback_speed = float(speed_text.replace('x', ''))
    
    def animate_game(self):
        """Main animation loop"""
        if not self.animation_running:
            return
            
        if self.is_playing and self.event_index < len(self.event_log):
            # Process events at current time
            self.process_current_events()
            
            # Advance time
            self.current_time += 0.1 * self.playback_speed  # 100ms steps
            
            # Update time display
            self.update_time_display()
            
        # Schedule next frame at higher frame rate for smoother animation
        self.root.after(self.animation_frame_time, self.animate_game)  # 60 FPS
    
    def process_current_events(self):
        """Process events that should happen at current time"""
        while (self.event_index < len(self.event_log) and 
               self.event_log[self.event_index].get('timestamp', 0) <= self.current_time):
            
            event = self.event_log[self.event_index]
            self.process_event(event)
            self.event_index += 1
    
    def process_event(self, event: Dict[str, Any]):
        """Process a single game event"""
        event_type = event.get('type', '')
        details = event.get('details', {})
        
        if event_type == 'SKATE':
            # Player movement
            player_id = details.get('player_id', '')
            target_pos = details.get('target_pos', (0, 0))
            
            # Ensure coordinates are valid (within rink bounds)
            x, y = self.clamp_to_rink_bounds(target_pos[0], target_pos[1])
            
            if player_id.startswith('home_'):
                self.animate_player_movement('home', player_id, x, y)
            elif player_id.startswith('away_'):
                self.animate_player_movement('away', player_id, x, y)
                
        elif event_type == 'PUCK_MOVEMENT':
            # Puck movement
            target_pos = details.get('target_pos', (100, 42.5))
            x, y = self.clamp_to_rink_bounds(target_pos[0], target_pos[1])
            self.animate_puck_movement(x, y)
            
        elif event_type in ['SHOT', 'PASS', 'HIT', 'GOAL', 'SAVE']:
            # Action events with visual feedback
            self.show_action_effect(event_type, details)
            
        elif event_type == 'FACE_OFF':
            # Face-off positioning
            self.setup_faceoff_positions(details.get('location', 'center'))
    
    def clamp_to_rink_bounds(self, x: float, y: float) -> Tuple[float, float]:
        """Ensure coordinates stay within realistic rink bounds with proper padding"""
        # Hockey rink bounds with proper margins to keep players visible
        margin = 5  # 5 feet margin from edges
        min_x, max_x = margin, self.rink_length_ft - margin  # 5 to 195 feet
        min_y, max_y = margin, self.rink_width_ft - margin   # 5 to 80 feet
        
        clamped_x = max(min_x, min(max_x, x))
        clamped_y = max(min_y, min(max_y, y))
        
        return clamped_x, clamped_y
    
    def ease_in_out_cubic(self, t: float) -> float:
        """Smooth easing function for natural movement (cubic ease-in-out)"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            p = 2 * t - 2
            return 1 + p * p * p / 2
    
    def ease_out_quart(self, t: float) -> float:
        """Quick start, smooth stop (good for player movement)"""
        return 1 - pow(1 - t, 4)
    
    def ease_in_out_sine(self, t: float) -> float:
        """Very smooth, natural movement"""
        return -(math.cos(math.pi * t) - 1) / 2
    
    def animate_player_movement(self, team: str, player_id: str, target_x: float, target_y: float):
        """ENHANCED: Smoothly animate player movement with fluid motion"""
        # Get current position
        players_dict = self.home_players if team == 'home' else self.away_players
        if player_id not in players_dict:
            return
            
        # Find current position in player data
        player_list = self.player_data[team]
        current_player = None
        for player in player_list:
            if player['id'] == player_id:
                current_player = player
                break
                
        if not current_player:
            return
            
        # Calculate movement parameters
        start_x, start_y = current_player['x'], current_player['y']
        distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
        
        # Cancel any existing animation for this player
        animation_key = f"{team}_{player_id}"
        if animation_key in self.active_animations:
            # Cancel previous animation
            self.root.after_cancel(self.active_animations[animation_key]['after_id'])
        
        # Calculate animation duration based on distance (more realistic)
        base_duration = 800  # 800ms base duration
        speed_factor = min(2.0, max(0.3, distance / 50))  # Scale with distance
        duration = int(base_duration * speed_factor)
        
        # Calculate total animation steps at 60 FPS
        total_steps = max(10, duration // self.animation_frame_time)
        
        # Store animation data
        animation_data = {
            'start_x': start_x,
            'start_y': start_y,
            'target_x': target_x,
            'target_y': target_y,
            'current_step': 0,
            'total_steps': total_steps,
            'start_time': time.time() * 1000,  # Current time in ms
            'duration': duration,
            'after_id': None
        }
        
        self.active_animations[animation_key] = animation_data
        
        # Start the fluid animation
        self._animate_player_step(team, player_id, animation_key)
        
    def _animate_player_step(self, team: str, player_id: str, animation_key: str):
        """Execute one step of the fluid player animation"""
        if animation_key not in self.active_animations:
            return
            
        animation = self.active_animations[animation_key]
        current_time = time.time() * 1000
        elapsed = current_time - animation['start_time']
        
        # Calculate progress (0.0 to 1.0)
        progress = min(1.0, elapsed / animation['duration'])
        
        # Apply easing function for natural movement
        eased_progress = self.ease_in_out_sine(progress)
        
        # Calculate current position using eased progress
        current_x = animation['start_x'] + (animation['target_x'] - animation['start_x']) * eased_progress
        current_y = animation['start_y'] + (animation['target_y'] - animation['start_y']) * eased_progress
        
        # Update player position
        self.update_player_position(team, player_id, current_x, current_y)
        
        # Continue animation if not finished
        if progress < 1.0:
            animation['after_id'] = self.root.after(
                self.animation_frame_time, 
                lambda: self._animate_player_step(team, player_id, animation_key)
            )
        else:
            # Animation complete - update final position and cleanup
            current_player = None
            for player in self.player_data[team]:
                if player['id'] == player_id:
                    current_player = player
                    break
            
            if current_player:
                current_player['x'] = animation['target_x']
                current_player['y'] = animation['target_y']
            
            # Remove completed animation
            del self.active_animations[animation_key]
    
    def animate_puck_movement(self, target_x: float, target_y: float):
        """ENHANCED: Smoothly animate puck movement with realistic physics"""
        start_x, start_y = self.puck_data['x'], self.puck_data['y']
        distance = math.sqrt((target_x - start_x)**2 + (target_y - start_y)**2)
        
        # Cancel any existing puck animation
        puck_key = 'puck_movement'
        if puck_key in self.active_animations:
            self.root.after_cancel(self.active_animations[puck_key]['after_id'])
        
        # Puck moves faster than players with different easing
        base_duration = 400  # 400ms base duration (faster than players)
        speed_factor = min(1.5, max(0.2, distance / 80))  # Scale with distance
        duration = int(base_duration * speed_factor)
        
        # Calculate animation steps
        total_steps = max(8, duration // self.animation_frame_time)
        
        # Store puck animation data
        animation_data = {
            'start_x': start_x,
            'start_y': start_y,
            'target_x': target_x,
            'target_y': target_y,
            'current_step': 0,
            'total_steps': total_steps,
            'start_time': time.time() * 1000,
            'duration': duration,
            'after_id': None
        }
        
        self.active_animations[puck_key] = animation_data
        
        # Start puck animation
        self._animate_puck_step(puck_key)
    
    def _animate_puck_step(self, animation_key: str):
        """Execute one step of the fluid puck animation"""
        if animation_key not in self.active_animations:
            return
            
        animation = self.active_animations[animation_key]
        current_time = time.time() * 1000
        elapsed = current_time - animation['start_time']
        
        # Calculate progress
        progress = min(1.0, elapsed / animation['duration'])
        
        # Use different easing for puck (more sudden start, smooth stop)
        eased_progress = self.ease_out_quart(progress)
        
        # Calculate current position
        current_x = animation['start_x'] + (animation['target_x'] - animation['start_x']) * eased_progress
        current_y = animation['start_y'] + (animation['target_y'] - animation['start_y']) * eased_progress
        
        # Update puck position
        self.update_puck_position(current_x, current_y)
        
        # Continue animation if not finished
        if progress < 1.0:
            animation['after_id'] = self.root.after(
                self.animation_frame_time,
                lambda: self._animate_puck_step(animation_key)
            )
        else:
            # Animation complete
            self.puck_data['x'] = animation['target_x']
            self.puck_data['y'] = animation['target_y']
            del self.active_animations[animation_key]
    
    def show_action_effect(self, action_type: str, details: Dict[str, Any]):
        """Show visual effect for game actions"""
        effect_x = self.rink_bounds['center_x']
        effect_y = 100
        
        # Determine effect based on action type
        if action_type == 'SHOT':
            text = "🏒 SHOT!"
            color = '#ff9800'
            duration = 1500
        elif action_type == 'GOAL':
            text = "🚨 GOAL! 🚨"
            color = '#4caf50'
            duration = 3000
            # Add celebration effect
            self.create_goal_celebration()
        elif action_type == 'SAVE':
            text = "🥅 SAVE!"
            color = '#2196f3'
            duration = 1200
        elif action_type == 'PASS':
            text = "📨 PASS"
            color = '#9c27b0'
            duration = 800
        elif action_type == 'HIT':
            text = "💥 HIT!"
            color = '#f44336'
            duration = 1000
        elif action_type == 'PENALTY':
            text = "⚠️ PENALTY"
            color = '#ff5722'
            duration = 2000
        else:
            text = action_type.upper()
            color = '#ffffff'
            duration = 1000
        
        # Create effect text
        effect_id = self.canvas.create_text(
            effect_x, effect_y,
            text=text, fill=color,
            font=('Segoe UI', 18, 'bold'),
            tags="effect"
        )
        
        # Animate effect (fade and move up)
        self.animate_effect(effect_id, effect_x, effect_y, duration)
    
    def create_goal_celebration(self):
        """Create special celebration effect for goals"""
        # Create multiple celebration texts
        celebrations = ["🎉", "⭐", "🏆", "🎊"]
        
        for i, celebration in enumerate(celebrations):
            x = self.rink_bounds['center_x'] + (i - 1.5) * 100
            y = 150 + i * 20
            
            effect_id = self.canvas.create_text(
                x, y,
                text=celebration, fill='#ffeb3b',
                font=('Segoe UI', 24, 'bold'),
                tags="celebration"
            )
            
            # Animate celebration
            self.animate_celebration(effect_id, x, y, 2000 + i * 200)
    
    def animate_effect(self, effect_id: int, start_x: float, start_y: float, duration: int):
        """Animate an effect object"""
        steps = 20
        step_duration = duration // steps
        
        for step in range(steps):
            progress = step / steps
            # Move up and fade
            new_y = start_y - (progress * 50)
            alpha = 1.0 - progress
            
            # Color with alpha (simplified - just change to gray as it fades)
            if progress > 0.7:
                color = '#888888'
            elif progress > 0.4:
                color = '#bbbbbb'
            else:
                color = None  # Keep original
            
            delay = step * step_duration
            self.root.after(delay, lambda y=new_y, c=color: 
                          self.update_effect_position(effect_id, start_x, y, c))
        
        # Remove effect after animation
        self.root.after(duration, lambda: self.canvas.delete(effect_id))
    
    def animate_celebration(self, effect_id: int, start_x: float, start_y: float, duration: int):
        """Animate celebration effects"""
        import random
        
        steps = 15
        step_duration = duration // steps
        
        for step in range(steps):
            progress = step / steps
            # Random movement for celebration
            offset_x = random.randint(-20, 20)
            offset_y = random.randint(-10, 10) - (progress * 30)
            
            new_x = start_x + offset_x
            new_y = start_y + offset_y
            
            delay = step * step_duration
            self.root.after(delay, lambda x=new_x, y=new_y: 
                          self.update_effect_position(effect_id, x, y))
        
        # Remove celebration after animation
        self.root.after(duration, lambda: self.canvas.delete(effect_id))
    
    def update_effect_position(self, effect_id: int, x: float, y: float, color: str = None):
        """Update effect position and optionally color"""
        try:
            self.canvas.coords(effect_id, x, y)
            if color:
                self.canvas.itemconfig(effect_id, fill=color)
        except:
            pass  # Effect may have been deleted
    
    def setup_faceoff_positions(self, location: str = 'center'):
        """Set up players for face-off at specified location"""
        if location == 'center':
            # Center ice face-off
            faceoff_x, faceoff_y = 100, 42.5
        elif location == 'home_zone':
            # Home zone face-off
            faceoff_x, faceoff_y = 30, 42.5
        elif location == 'away_zone':
            # Away zone face-off
            faceoff_x, faceoff_y = 170, 42.5
        else:
            # Default to center
            faceoff_x, faceoff_y = 100, 42.5
        
        # Position centers for face-off
        home_center = self.player_data['home'][0]  # First player is center
        away_center = self.player_data['away'][0]
        
        # Animate centers to face-off position
        self.animate_player_movement('home', home_center['id'], faceoff_x - 2, faceoff_y)
        self.animate_player_movement('away', away_center['id'], faceoff_x + 2, faceoff_y)
        
        # Position puck
        self.animate_puck_movement(faceoff_x, faceoff_y)
    
    def update_all_positions(self):
        """Update all player and puck positions from current data"""
        # Update home players
        for i, player in enumerate(self.player_data['home']):
            self.update_player_position('home', player['id'], player['x'], player['y'])
            
        # Update away players
        for i, player in enumerate(self.player_data['away']):
            self.update_player_position('away', player['id'], player['x'], player['y'])
            
        # Update puck
        self.update_puck_position(self.puck_data['x'], self.puck_data['y'])
    
    def update_time_display(self):
        """Update the game time display"""
        # Convert seconds to MM:SS format
        minutes = int(self.current_time // 60)
        seconds = int(self.current_time % 60)
        
        # Determine period (20 minutes each)
        period = min(3, (minutes // 20) + 1)
        period_time = minutes % 20
        
        time_str = f"{period_time:02d}:{seconds:02d}"
        period_str = "1st" if period == 1 else "2nd" if period == 2 else "3rd"
        
        self.time_label.config(text=f"{time_str} - {period_str} Period")
    
    def on_canvas_click(self, event):
        """Handle canvas clicks"""
        # Convert to game coordinates and show info
        game_x, game_y = self.canvas_to_game_coords(event.x, event.y)
        self.status_label.config(text=f"Click: Canvas({event.x}, {event.y}) → Game({game_x:.1f}, {game_y:.1f})")
    
    def on_canvas_hover(self, event):
        """Handle canvas mouse hover"""
        # Show coordinates in status
        game_x, game_y = self.canvas_to_game_coords(event.x, event.y)
        self.status_label.config(text=f"Position: Game({game_x:.1f}, {game_y:.1f})")
    
    def focus_home_zone(self):
        """Focus camera on home zone"""
        # Could implement camera panning in future
        self.status_label.config(text="Focused on Home Zone")
    
    def focus_center_ice(self):
        """Focus camera on center ice"""
        self.status_label.config(text="Focused on Center Ice")
    
    def focus_away_zone(self):
        """Focus camera on away zone"""
        self.status_label.config(text="Focused on Away Zone")
    
    def add_event_to_log(self, event_text: str):
        """Add an event to the events log"""
        self.events_text.config(state='normal')
        self.events_text.insert('end', f"{event_text}\n")
        self.events_text.see('end')
        self.events_text.config(state='disabled')
    
    def setup_rink_coordinate_mapping(self):
        """Setup coordinate mapping from NHL simulation to PUCKDYNASTYRINKCOMPLETE.png"""
        # Center the rink image on the canvas
        rink_left = (self.canvas_width - self.rink_display_width) // 2
        rink_top = (self.canvas_height - self.rink_display_height) // 2
        
        # Update rink boundaries for proper positioning
        self.rink_bounds.update({
            'left': rink_left,
            'right': rink_left + self.rink_display_width,
            'top': rink_top,
            'bottom': rink_top + self.rink_display_height,
            'center_x': rink_left + self.rink_display_width // 2,
            'center_y': rink_top + self.rink_display_height // 2
        })
        
        # Calculate scale factors to map NHL simulation coordinates to display
        # Simulation coordinates: X(0-200ft), Y(0-85ft) → Display pixels
        self.scale_x = self.rink_display_width / 200.0   # pixels per foot in X
        self.scale_y = self.rink_display_height / 85.0   # pixels per foot in Y
        
        # No offsets needed - direct mapping from simulation to image
        self.offset_x = 0
        self.offset_y = 0
        
        print(f"🏒 NHL SIMULATION COORDINATE MAPPING:")
        print(f"   Simulation: 200ft x 85ft → Image: {self.rink_display_width}x{self.rink_display_height}px")
        print(f"   Scale factors: X={self.scale_x:.2f}px/ft, Y={self.scale_y:.2f}px/ft")
        print(f"   Display bounds: {self.rink_bounds}")
    
    def run(self):
        """Run the game viewer (if it owns the root window)"""
        if self.owns_root:
            self.root.mainloop()


# Compatibility function for main.py integration
def launch_game_viewer(event_log, duration=3600, home_team="HOME", away_team="AWAY"):
    """
    Launch the rebuilt game viewer - compatible with main.py
    """
    print("🏒 Launching Rebuilt NHL Game Viewer...")
    
    root = tk.Tk()
    viewer = RebuiltNHLGameViewer(root, event_log, duration, home_team, away_team)
    
    # Start animation if events exist
    if event_log:
        viewer.start_playback()
    
    root.mainloop()


# Test function
def test_rebuilt_viewer():
    """Test the rebuilt viewer with sample data"""
    # Create sample event log
    sample_events = [
        {'timestamp': 0.0, 'type': 'FACE_OFF', 'details': {}},
        {'timestamp': 2.0, 'type': 'SKATE', 'details': {'player_id': 'home_0', 'target_pos': (95, 42.5)}},
        {'timestamp': 4.0, 'type': 'PUCK_MOVEMENT', 'details': {'target_pos': (95, 42.5)}},
        {'timestamp': 6.0, 'type': 'SKATE', 'details': {'player_id': 'away_0', 'target_pos': (105, 42.5)}},
        {'timestamp': 8.0, 'type': 'SHOT', 'details': {'player_id': 'home_1', 'target_pos': (185, 42.5)}},
        {'timestamp': 10.0, 'type': 'PUCK_MOVEMENT', 'details': {'target_pos': (185, 42.5)}}
    ]
    
    launch_game_viewer(sample_events, 600, "Philadelphia Flyers", "New York Rangers")


if __name__ == "__main__":
    print("🏒 Testing Rebuilt NHL Game Viewer...")
    test_rebuilt_viewer()