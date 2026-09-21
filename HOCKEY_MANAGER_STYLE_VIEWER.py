"""
NEW NHL Game Viewer - Exact Copy of Hockey Management Game Style
Recreates the rink appearance from Eastside Hockey Manager reference
"""

import tkinter as tk
from tkinter import ttk
import math
import time
from typing import Dict, List, Tuple, Optional

class NHLGameViewer:
    """NHL Game Viewer with exact hockey management game appearance"""
    
    def __init__(self, root, game_data=None):
        self.root = root
        self.root.title("🏒 NHL Game Viewer - Hockey Manager Style")
        self.root.geometry("1000x600")
        self.root.configure(bg='#2d5016')  # Dark green background like reference
        
        # Game data
        self.game_data = game_data or {}
        self.event_log = self.game_data.get('event_log', [])
        self.home_team = self.game_data.get('home_team', 'HOME')
        self.away_team = self.game_data.get('away_team', 'AWAY')
        
        # Rink dimensions - optimized to match reference image proportions
        self.rink_length = 600   # Length of the rink 
        self.rink_width = 280    # Width of the rink
        self.rink_corner_radius = 70  # Radius for the rounded ends
        
        # Canvas positioning - center the rink
        self.canvas_width = 900
        self.canvas_height = 400
        self.rink_x = (self.canvas_width - self.rink_length) // 2
        self.rink_y = (self.canvas_height - self.rink_width) // 2
        
        # Player and puck
        self.player_radius = 6
        self.puck_radius = 2
        self.players = {}
        self.puck = None
        self.player_positions = {}
        self.puck_position = (self.rink_x + self.rink_length//2, self.rink_y + self.rink_width//2)
        
        # Animation
        self.playback_time = 0.0
        self.is_playing = False
        self.playback_speed = 1.0
        self.current_event_index = 0
        
        # Create interface
        self.create_interface()
        self.draw_hockey_manager_rink()
        self.initialize_players()
        
    def create_interface(self):
        """Create interface matching hockey management games"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#2d5016')
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Top info bar
        info_frame = tk.Frame(main_frame, bg='#1a3009', height=60)
        info_frame.pack(fill='x', pady=(0, 5))
        info_frame.pack_propagate(False)
        
        # Team matchup
        matchup_label = tk.Label(info_frame, text=f"{self.home_team} vs {self.away_team}", 
                                font=('Arial', 14, 'bold'), fg='#ffffff', bg='#1a3009')
        matchup_label.pack(side='left', padx=15, pady=15)
        
        # Controls
        controls_frame = tk.Frame(info_frame, bg='#1a3009')
        controls_frame.pack(side='right', padx=15, pady=10)
        
        self.play_button = tk.Button(controls_frame, text="▶", 
                                    command=self.toggle_playback,
                                    bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'),
                                    width=3)
        self.play_button.pack(side='left', padx=2)
        
        # Speed control
        self.speed_scale = tk.Scale(controls_frame, from_=0.5, to=2.0, resolution=0.5,
                                   orient='horizontal', bg='#1a3009', fg='white',
                                   command=self.update_speed, length=80)
        self.speed_scale.set(1.0)
        self.speed_scale.pack(side='left', padx=5)
        
        # Game canvas with dark green background like reference
        self.canvas = tk.Canvas(main_frame, width=self.canvas_width, height=self.canvas_height,
                               bg='#2d5016', highlightthickness=2, highlightbackground='#1a3009')
        self.canvas.pack(pady=5)
        
        # Status bar
        status_frame = tk.Frame(main_frame, bg='#1a3009', height=25)
        status_frame.pack(fill='x', pady=(5, 0))
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Game Ready",
                                    font=('Arial', 9), fg='#ffffff', bg='#1a3009')
        self.status_label.pack(side='left', padx=10, pady=3)
        
    def draw_hockey_manager_rink(self):
        """Draw rink exactly like hockey management games (Eastside Hockey Manager style)"""
        # Clear canvas
        self.canvas.delete("all")
        
        # Colors exactly like the reference image
        ice_color = '#ffffff'      # Pure white ice
        board_color = '#8B4513'    # Brown boards
        red_line_color = '#CC0000' # Red lines
        blue_line_color = '#0000FF' # Blue lines
        
        # 1. DRAW MAIN RINK SHAPE (oval-ended rectangle)
        
        # Main rectangular body of rink
        self.canvas.create_rectangle(
            self.rink_x + self.rink_corner_radius, self.rink_y,
            self.rink_x + self.rink_length - self.rink_corner_radius, self.rink_y + self.rink_width,
            fill=ice_color, outline=board_color, width=3
        )
        
        # Left semicircle end
        self.canvas.create_arc(
            self.rink_x, self.rink_y,
            self.rink_x + (2 * self.rink_corner_radius), self.rink_y + self.rink_width,
            start=90, extent=180, fill=ice_color, outline=board_color, width=3, style='pieslice'
        )
        
        # Right semicircle end
        self.canvas.create_arc(
            self.rink_x + self.rink_length - (2 * self.rink_corner_radius), self.rink_y,
            self.rink_x + self.rink_length, self.rink_y + self.rink_width,
            start=270, extent=180, fill=ice_color, outline=board_color, width=3, style='pieslice'
        )
        
        # 2. DRAW ALL HOCKEY MARKINGS
        center_x = self.rink_x + self.rink_length // 2
        center_y = self.rink_y + self.rink_width // 2
        
        # CENTER RED LINE (thick line down the middle)
        self.canvas.create_line(
            center_x, self.rink_y + 5,
            center_x, self.rink_y + self.rink_width - 5,
            fill=red_line_color, width=4
        )
        
        # CENTER CIRCLE (large circle in middle)
        center_circle_radius = 35
        self.canvas.create_oval(
            center_x - center_circle_radius, center_y - center_circle_radius,
            center_x + center_circle_radius, center_y + center_circle_radius,
            outline=blue_line_color, width=2, fill=''
        )
        
        # Center face-off dot
        self.canvas.create_oval(
            center_x - 2, center_y - 2,
            center_x + 2, center_y + 2,
            fill=blue_line_color, outline=blue_line_color
        )
        
        # BLUE LINES (zone dividers)
        # Left blue line (defensive zone)
        left_blue_x = self.rink_x + self.rink_length // 3 + 20
        self.canvas.create_line(
            left_blue_x, self.rink_y + 5,
            left_blue_x, self.rink_y + self.rink_width - 5,
            fill=blue_line_color, width=3
        )
        
        # Right blue line (offensive zone)
        right_blue_x = self.rink_x + (2 * self.rink_length) // 3 - 20
        self.canvas.create_line(
            right_blue_x, self.rink_y + 5,
            right_blue_x, self.rink_y + self.rink_width - 5,
            fill=blue_line_color, width=3
        )
        
        # GOAL LINES (thin red lines near goals)
        goal_line_offset = 35
        
        # Left goal line
        left_goal_x = self.rink_x + goal_line_offset
        self.canvas.create_line(
            left_goal_x, self.rink_y + 5,
            left_goal_x, self.rink_y + self.rink_width - 5,
            fill=red_line_color, width=2
        )
        
        # Right goal line
        right_goal_x = self.rink_x + self.rink_length - goal_line_offset
        self.canvas.create_line(
            right_goal_x, self.rink_y + 5,
            right_goal_x, self.rink_y + self.rink_width - 5,
            fill=red_line_color, width=2
        )
        
        # GOAL CREASES (blue semicircles)
        crease_radius = 20
        
        # Left goal crease
        self.canvas.create_arc(
            left_goal_x - crease_radius, center_y - crease_radius,
            left_goal_x + crease_radius, center_y + crease_radius,
            start=-90, extent=180, outline=blue_line_color, width=2, style='arc'
        )
        
        # Right goal crease
        self.canvas.create_arc(
            right_goal_x - crease_radius, center_y - crease_radius,
            right_goal_x + crease_radius, center_y + crease_radius,
            start=90, extent=180, outline=blue_line_color, width=2, style='arc'
        )
        
        # FACE-OFF CIRCLES (4 in end zones)
        faceoff_radius = 20
        faceoff_dot_radius = 2
        
        # End zone face-off positions
        end_zone_x_offset = 80
        end_zone_y_offset = 45
        
        faceoff_positions = [
            # Left end zone
            (self.rink_x + end_zone_x_offset, center_y - end_zone_y_offset),
            (self.rink_x + end_zone_x_offset, center_y + end_zone_y_offset),
            # Right end zone
            (self.rink_x + self.rink_length - end_zone_x_offset, center_y - end_zone_y_offset),
            (self.rink_x + self.rink_length - end_zone_x_offset, center_y + end_zone_y_offset),
        ]
        
        for x, y in faceoff_positions:
            # Face-off circle
            self.canvas.create_oval(
                x - faceoff_radius, y - faceoff_radius,
                x + faceoff_radius, y + faceoff_radius,
                outline=red_line_color, width=2, fill=''
            )
            # Face-off dot
            self.canvas.create_oval(
                x - faceoff_dot_radius, y - faceoff_dot_radius,
                x + faceoff_dot_radius, y + faceoff_dot_radius,
                fill=red_line_color, outline=red_line_color
            )
        
        # NEUTRAL ZONE FACE-OFF DOTS (4 small red dots)
        neutral_dot_radius = 1.5
        neutral_y_offset = 25
        neutral_x_offset = 50
        
        neutral_positions = [
            (center_x - neutral_x_offset, center_y - neutral_y_offset),
            (center_x - neutral_x_offset, center_y + neutral_y_offset),
            (center_x + neutral_x_offset, center_y - neutral_y_offset),
            (center_x + neutral_x_offset, center_y + neutral_y_offset),
        ]
        
        for x, y in neutral_positions:
            self.canvas.create_oval(
                x - neutral_dot_radius, y - neutral_dot_radius,
                x + neutral_dot_radius, y + neutral_dot_radius,
                fill=red_line_color, outline=red_line_color
            )
        
        # GOALS (small white rectangles)
        goal_width = 16
        goal_depth = 4
        
        # Left goal
        self.canvas.create_rectangle(
            self.rink_x - 1, center_y - goal_width//2,
            self.rink_x + goal_depth, center_y + goal_width//2,
            fill='#f0f0f0', outline=red_line_color, width=2
        )
        
        # Right goal
        self.canvas.create_rectangle(
            self.rink_x + self.rink_length - goal_depth, center_y - goal_width//2,
            self.rink_x + self.rink_length + 1, center_y + goal_width//2,
            fill='#f0f0f0', outline=red_line_color, width=2
        )
        
    def initialize_players(self):
        """Initialize players on ice like hockey management games"""
        # Clear existing players
        for player_id in list(self.players.keys()):
            if self.players[player_id]:
                self.canvas.delete(self.players[player_id])
        self.players.clear()
        self.player_positions.clear()
        
        # Home team (blue) - left side positions
        home_positions = [
            (self.rink_x + 80, self.rink_y + self.rink_width//2 - 60),   # LW
            (self.rink_x + 120, self.rink_y + self.rink_width//2),       # C
            (self.rink_x + 80, self.rink_y + self.rink_width//2 + 60),   # RW
            (self.rink_x + 60, self.rink_y + self.rink_width//2 - 30),   # LD
            (self.rink_x + 60, self.rink_y + self.rink_width//2 + 30),   # RD
            (self.rink_x + 25, self.rink_y + self.rink_width//2),        # G
        ]
        
        for i, (x, y) in enumerate(home_positions):
            player_id = f"home_{i}"
            player_obj = self.canvas.create_oval(
                x - self.player_radius, y - self.player_radius,
                x + self.player_radius, y + self.player_radius,
                fill='#0066CC', outline='white', width=1
            )
            self.players[player_id] = player_obj
            self.player_positions[player_id] = (x, y)
            
        # Away team (red) - right side positions
        away_positions = [
            (self.rink_x + self.rink_length - 80, self.rink_y + self.rink_width//2 - 60),  # LW
            (self.rink_x + self.rink_length - 120, self.rink_y + self.rink_width//2),      # C
            (self.rink_x + self.rink_length - 80, self.rink_y + self.rink_width//2 + 60),  # RW
            (self.rink_x + self.rink_length - 60, self.rink_y + self.rink_width//2 - 30),  # LD
            (self.rink_x + self.rink_length - 60, self.rink_y + self.rink_width//2 + 30),  # RD
            (self.rink_x + self.rink_length - 25, self.rink_y + self.rink_width//2),       # G
        ]
        
        for i, (x, y) in enumerate(away_positions):
            player_id = f"away_{i}"
            player_obj = self.canvas.create_oval(
                x - self.player_radius, y - self.player_radius,
                x + self.player_radius, y + self.player_radius,
                fill='#CC0000', outline='white', width=1
            )
            self.players[player_id] = player_obj
            self.player_positions[player_id] = (x, y)
            
        # Puck at center ice
        center_x = self.rink_x + self.rink_length // 2
        center_y = self.rink_y + self.rink_width // 2
        
        self.puck = self.canvas.create_oval(
            center_x - self.puck_radius, center_y - self.puck_radius,
            center_x + self.puck_radius, center_y + self.puck_radius,
            fill='#000000', outline='white', width=1
        )
        self.puck_position = (center_x, center_y)
        
    def constrain_to_rink(self, x: float, y: float) -> Tuple[float, float]:
        """Keep players within rink boundaries"""
        margin = self.player_radius + 2
        
        # Basic constraints
        min_x = self.rink_x + margin
        max_x = self.rink_x + self.rink_length - margin
        min_y = self.rink_y + margin
        max_y = self.rink_y + self.rink_width - margin
        
        x = max(min_x, min(max_x, x))
        y = max(min_y, min(max_y, y))
        
        return x, y
        
    def move_player(self, player_id: str, new_x: float, new_y: float):
        """Move player with rink constraints"""
        constrained_x, constrained_y = self.constrain_to_rink(new_x, new_y)
        
        if player_id in self.players and self.players[player_id]:
            self.canvas.coords(
                self.players[player_id],
                constrained_x - self.player_radius, constrained_y - self.player_radius,
                constrained_x + self.player_radius, constrained_y + self.player_radius
            )
            
        self.player_positions[player_id] = (constrained_x, constrained_y)
        
    def move_puck(self, new_x: float, new_y: float):
        """Move puck with constraints"""
        margin = 5
        min_x = self.rink_x + margin
        max_x = self.rink_x + self.rink_length - margin
        min_y = self.rink_y + margin
        max_y = self.rink_y + self.rink_width - margin
        
        constrained_x = max(min_x, min(max_x, new_x))
        constrained_y = max(min_y, min(max_y, new_y))
        
        if self.puck:
            self.canvas.coords(
                self.puck,
                constrained_x - self.puck_radius, constrained_y - self.puck_radius,
                constrained_x + self.puck_radius, constrained_y + self.puck_radius
            )
            
        self.puck_position = (constrained_x, constrained_y)
        
    def toggle_playback(self):
        """Toggle play/pause"""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_button.config(text="⏸")
            self.start_animation()
        else:
            self.play_button.config(text="▶")
            
    def update_speed(self, value):
        """Update playback speed"""
        self.playback_speed = float(value)
        
    def start_animation(self):
        """Start animation loop"""
        if self.is_playing:
            self.animate_frame()
            
    def animate_frame(self):
        """Animate one frame"""
        if not self.is_playing:
            return
            
        self.playback_time += 0.1 * self.playback_speed
        
        # Simple demo animation
        import random
        for player_id in self.players:
            if player_id in self.player_positions:
                current_x, current_y = self.player_positions[player_id]
                new_x = current_x + random.uniform(-1, 1)
                new_y = current_y + random.uniform(-1, 1)
                self.move_player(player_id, new_x, new_y)
                
        # Move puck
        current_x, current_y = self.puck_position
        new_x = current_x + random.uniform(-2, 2)
        new_y = current_y + random.uniform(-2, 2)
        self.move_puck(new_x, new_y)
        
        # Update status
        period = int(self.playback_time // 1200) + 1
        time_in_period = self.playback_time % 1200
        minutes = int((1200 - time_in_period) // 60)
        seconds = int((1200 - time_in_period) % 60)
        self.status_label.config(text=f"Period {period} - {minutes:02d}:{seconds:02d}")
        
        if self.is_playing:
            self.root.after(50, self.animate_frame)

# Compatibility functions for integration
def launch_game_viewer(event_log=None, game_length=1200, home_team_name="HOME", away_team_name="AWAY"):
    """Launch compatible with main game"""
    root = tk.Tk()
    
    game_data = {
        'event_log': event_log or [],
        'home_team': home_team_name,
        'away_team': away_team_name,
        'game_length': game_length
    }
    
    viewer = NHLGameViewer(root, game_data)
    root.mainloop()
    return viewer

def launch_game_viewer_standalone(game_data=None):
    """Standalone launcher"""
    root = tk.Tk()
    viewer = NHLGameViewer(root, game_data)
    return viewer

def create_test_viewer():
    """Test the viewer"""
    root = tk.Tk()
    test_data = {
        'home_team': 'Toronto Maple Leafs',
        'away_team': 'Montreal Canadiens',
        'event_log': []
    }
    viewer = NHLGameViewer(root, test_data)
    root.mainloop()

if __name__ == "__main__":
    create_test_viewer()