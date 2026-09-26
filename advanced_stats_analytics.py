# advanced_stats_analytics.py
# Part 3: Advanced Statistics & Analytics Integration
# Real-time analytics and insights like professional broadcasts

import tkinter as tk
from tkinter import ttk
import time
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
from datetime import datetime, timedelta

# --- Core Analytics Data Structures ---

@dataclass
class PlayerStats:
    """Real-time player statistics"""
    player_id: str
    name: str
    position: str
    
    # Basic stats
    goals: int = 0
    assists: int = 0
    shots: int = 0
    hits: int = 0
    blocks: int = 0
    saves: int = 0  # For goalies
    
    # Advanced stats
    ice_time: float = 0.0  # seconds
    zone_time: Dict[str, float] = field(default_factory=lambda: {"offensive": 0.0, "neutral": 0.0, "defensive": 0.0})
    possession_time: float = 0.0
    passes_attempted: int = 0
    passes_completed: int = 0
    faceoffs_won: int = 0
    faceoffs_lost: int = 0
    
    # Heat map data
    position_data: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, time)
    shot_locations: List[Tuple[float, float, str]] = field(default_factory=list)  # (x, y, result)
    
    @property
    def points(self) -> int:
        return self.goals + self.assists
    
    @property
    def plus_minus(self) -> int:
        # This would be calculated based on goals for/against while on ice
        return 0  # Placeholder
    
    @property
    def shooting_percentage(self) -> float:
        return (self.goals / self.shots * 100) if self.shots > 0 else 0.0
    
    @property
    def passing_percentage(self) -> float:
        return (self.passes_completed / self.passes_attempted * 100) if self.passes_attempted > 0 else 0.0
    
    @property
    def faceoff_percentage(self) -> float:
        total_faceoffs = self.faceoffs_won + self.faceoffs_lost
        return (self.faceoffs_won / total_faceoffs * 100) if total_faceoffs > 0 else 0.0

@dataclass
class TeamStats:
    """Real-time team statistics"""
    team_name: str
    
    # Basic team stats
    goals: int = 0
    shots: int = 0
    hits: int = 0
    blocks: int = 0
    penalties: int = 0
    penalty_minutes: int = 0
    
    # Advanced team stats
    possession_percentage: float = 0.0
    possession_time: float = 0.0  # Total possession time for compatibility
    zone_time_percentage: Dict[str, float] = field(default_factory=lambda: {"offensive": 0.0, "neutral": 0.0, "defensive": 0.0})
    power_play_opportunities: int = 0
    power_play_goals: int = 0
    penalty_kill_opportunities: int = 0
    penalty_kill_goals_against: int = 0
    
    # Momentum and flow
    momentum_score: float = 0.0  # -100 to +100
    shot_attempts: int = 0
    scoring_chances: int = 0
    high_danger_chances: int = 0
    
    @property
    def shooting_percentage(self) -> float:
        return (self.goals / self.shots * 100) if self.shots > 0 else 0.0
    
    @property
    def power_play_percentage(self) -> float:
        return (self.power_play_goals / self.power_play_opportunities * 100) if self.power_play_opportunities > 0 else 0.0
    
    @property
    def penalty_kill_percentage(self) -> float:
        successful_kills = self.penalty_kill_opportunities - self.penalty_kill_goals_against
        return (successful_kills / self.penalty_kill_opportunities * 100) if self.penalty_kill_opportunities > 0 else 0.0

@dataclass
class GameEvent:
    """Individual game event for analytics"""
    timestamp: float
    event_type: str
    player_id: Optional[str] = None
    team: Optional[str] = None
    location: Optional[Tuple[float, float]] = None
    details: Dict[str, Any] = field(default_factory=dict)

class RealTimeStatsEngine:
    """Core engine for real-time statistics calculation"""
    
    def __init__(self):
        self.player_stats: Dict[str, PlayerStats] = {}
        self.team_stats: Dict[str, TeamStats] = {}
        self.game_events: List[GameEvent] = []
        self.event_subscribers: List[callable] = []
        
        # Performance tracking
        self.calculation_times = deque(maxlen=100)
        
    def initialize_game(self, home_team: str, away_team: str, home_players: List[Dict], away_players: List[Dict]):
        """Initialize stats for a new game"""
        self.team_stats[home_team] = TeamStats(home_team)
        self.team_stats[away_team] = TeamStats(away_team)
        
        # Initialize player stats
        for player_data in home_players:
            player_id = player_data['id']
            self.player_stats[player_id] = PlayerStats(
                player_id=player_id,
                name=player_data['name'],
                position=player_data['position']
            )
            
        for player_data in away_players:
            player_id = player_data['id']
            self.player_stats[player_id] = PlayerStats(
                player_id=player_id,
                name=player_data['name'],
                position=player_data['position']
            )
    
    def process_event(self, event: GameEvent):
        """Process a game event and update statistics"""
        start_time = time.perf_counter()
        
        self.game_events.append(event)
        
        # Update stats based on event type
        if event.event_type == "GOAL":
            self._process_goal_event(event)
        elif event.event_type == "SHOT":
            self._process_shot_event(event)
        elif event.event_type == "HIT":
            self._process_hit_event(event)
        elif event.event_type == "PASS":
            self._process_pass_event(event)
        elif event.event_type == "FACEOFF":
            self._process_faceoff_event(event)
        elif event.event_type == "PENALTY":
            self._process_penalty_event(event)
        elif event.event_type == "POSITION_UPDATE":
            self._process_position_update(event)
        
        # Update momentum
        self._update_momentum(event)
        
        # Notify subscribers
        for subscriber in self.event_subscribers:
            subscriber(event)
        
        # Track performance
        calculation_time = time.perf_counter() - start_time
        self.calculation_times.append(calculation_time)
    
    def _process_goal_event(self, event: GameEvent):
        """Process a goal event"""
        if event.player_id and event.player_id in self.player_stats:
            self.player_stats[event.player_id].goals += 1
            
            # Add to shot locations
            if event.location:
                self.player_stats[event.player_id].shot_locations.append(
                    (event.location[0], event.location[1], "GOAL")
                )
        
        if event.team and event.team in self.team_stats:
            self.team_stats[event.team].goals += 1
    
    def _process_shot_event(self, event: GameEvent):
        """Process a shot event"""
        if event.player_id and event.player_id in self.player_stats:
            self.player_stats[event.player_id].shots += 1
            
            # Add to shot locations
            if event.location:
                result = event.details.get('result', 'SHOT')
                self.player_stats[event.player_id].shot_locations.append(
                    (event.location[0], event.location[1], result)
                )
        
        if event.team and event.team in self.team_stats:
            self.team_stats[event.team].shots += 1
            self.team_stats[event.team].shot_attempts += 1
            
            # Determine if it's a scoring chance
            if self._is_scoring_chance(event.location):
                self.team_stats[event.team].scoring_chances += 1
                
            if self._is_high_danger_chance(event.location):
                self.team_stats[event.team].high_danger_chances += 1
    
    def _process_hit_event(self, event: GameEvent):
        """Process a hit event"""
        if event.player_id and event.player_id in self.player_stats:
            self.player_stats[event.player_id].hits += 1
        
        if event.team and event.team in self.team_stats:
            self.team_stats[event.team].hits += 1
    
    def _process_pass_event(self, event: GameEvent):
        """Process a pass event"""
        if event.player_id and event.player_id in self.player_stats:
            self.player_stats[event.player_id].passes_attempted += 1
            
            if event.details.get('successful', False):
                self.player_stats[event.player_id].passes_completed += 1
    
    def _process_faceoff_event(self, event: GameEvent):
        """Process a faceoff event"""
        winner_id = event.details.get('winner_id')
        loser_id = event.details.get('loser_id')
        
        if winner_id and winner_id in self.player_stats:
            self.player_stats[winner_id].faceoffs_won += 1
            
        if loser_id and loser_id in self.player_stats:
            self.player_stats[loser_id].faceoffs_lost += 1
    
    def _process_penalty_event(self, event: GameEvent):
        """Process a penalty event"""
        if event.team and event.team in self.team_stats:
            self.team_stats[event.team].penalties += 1
            minutes = event.details.get('minutes', 2)
            self.team_stats[event.team].penalty_minutes += minutes
    
    def _process_position_update(self, event: GameEvent):
        """Process player position update for heat maps"""
        if event.player_id and event.player_id in self.player_stats and event.location:
            self.player_stats[event.player_id].position_data.append(
                (event.location[0], event.location[1], event.timestamp)
            )
            
            # Limit position data to prevent memory issues
            if len(self.player_stats[event.player_id].position_data) > 1000:
                self.player_stats[event.player_id].position_data = \
                    self.player_stats[event.player_id].position_data[-500:]
    
    def _is_scoring_chance(self, location: Optional[Tuple[float, float]]) -> bool:
        """Determine if a shot location is a scoring chance"""
        if not location:
            return False
        
        # Define scoring chance areas (this would be based on actual rink coordinates)
        # For now, use simplified logic
        x, y = location
        # Assume shots from certain areas are scoring chances
        return True  # Placeholder
    
    def _is_high_danger_chance(self, location: Optional[Tuple[float, float]]) -> bool:
        """Determine if a shot location is a high danger chance"""
        if not location:
            return False
        
        # Define high danger areas
        x, y = location
        # Assume shots from very close are high danger
        return True  # Placeholder
    
    def _update_momentum(self, event: GameEvent):
        """Update team momentum based on event"""
        if not event.team or event.team not in self.team_stats:
            return
        
        momentum_change = 0.0
        
        if event.event_type == "GOAL":
            momentum_change = 15.0
        elif event.event_type == "SHOT":
            momentum_change = 2.0
        elif event.event_type == "HIT":
            momentum_change = 1.0
        elif event.event_type == "PENALTY":
            momentum_change = -5.0
        
        # Apply momentum change
        current_momentum = self.team_stats[event.team].momentum_score
        new_momentum = max(-100, min(100, current_momentum + momentum_change))
        self.team_stats[event.team].momentum_score = new_momentum
        
        # Decay momentum over time
        self._decay_momentum()
    
    def _decay_momentum(self):
        """Gradually decay momentum over time"""
        for team_stats in self.team_stats.values():
            if team_stats.momentum_score > 0:
                team_stats.momentum_score = max(0, team_stats.momentum_score - 0.1)
            elif team_stats.momentum_score < 0:
                team_stats.momentum_score = min(0, team_stats.momentum_score + 0.1)
    
    def get_game_summary(self) -> Dict[str, Any]:
        """Get comprehensive game statistics summary"""
        return {
            'teams': dict(self.team_stats),
            'players': dict(self.player_stats),
            'events_count': len(self.game_events),
            'performance': {
                'avg_calculation_time': sum(self.calculation_times) / len(self.calculation_times) if self.calculation_times else 0,
                'max_calculation_time': max(self.calculation_times) if self.calculation_times else 0
            }
        }

class HeatMapGenerator:
    """Generate heat maps for player and team analysis"""
    
    def __init__(self, rink_width: int = 1100, rink_height: int = 500):
        self.rink_width = rink_width
        self.rink_height = rink_height
        self.grid_size = 20  # Size of heat map grid cells
        
    def generate_player_heat_map(self, player_stats: PlayerStats) -> List[List[float]]:
        """Generate heat map data for a player's ice usage"""
        # Create grid
        cols = self.rink_width // self.grid_size
        rows = self.rink_height // self.grid_size
        heat_map = [[0.0 for _ in range(cols)] for _ in range(rows)]
        
        # Process position data
        for x, y, timestamp in player_stats.position_data:
            grid_x = int(x // self.grid_size)
            grid_y = int(y // self.grid_size)
            
            if 0 <= grid_x < cols and 0 <= grid_y < rows:
                heat_map[grid_y][grid_x] += 1.0
        
        # Normalize
        max_value = max(max(row) for row in heat_map) if any(any(row) for row in heat_map) else 1
        if max_value > 0:
            heat_map = [[cell / max_value for cell in row] for row in heat_map]
        
        return heat_map
    
    def generate_shot_heat_map(self, player_stats: PlayerStats) -> List[List[float]]:
        """Generate heat map for shot locations"""
        cols = self.rink_width // self.grid_size
        rows = self.rink_height // self.grid_size
        heat_map = [[0.0 for _ in range(cols)] for _ in range(rows)]
        
        for x, y, result in player_stats.shot_locations:
            grid_x = int(x // self.grid_size)
            grid_y = int(y // self.grid_size)
            
            if 0 <= grid_x < cols and 0 <= grid_y < rows:
                # Weight goals higher than regular shots
                weight = 3.0 if result == "GOAL" else 1.0
                heat_map[grid_y][grid_x] += weight
        
        # Normalize
        max_value = max(max(row) for row in heat_map) if any(any(row) for row in heat_map) else 1
        if max_value > 0:
            heat_map = [[cell / max_value for cell in row] for row in heat_map]
        
        return heat_map

class PossessionTracker:
    """Track possession statistics and zone time"""
    
    def __init__(self):
        self.possession_events = deque(maxlen=1000)
        self.zone_times = defaultdict(lambda: defaultdict(float))
        self.current_possession = None
        self.possession_start_time = None
        
    def update_possession(self, team: str, timestamp: float):
        """Update possession information"""
        if self.current_possession != team:
            # End previous possession
            if self.current_possession and self.possession_start_time:
                duration = timestamp - self.possession_start_time
                self.possession_events.append({
                    'team': self.current_possession,
                    'duration': duration,
                    'timestamp': timestamp
                })
            
            # Start new possession
            self.current_possession = team
            self.possession_start_time = timestamp
    
    def get_possession_percentage(self, team: str, time_window: float = 300.0) -> float:
        """Get possession percentage for a team in the given time window"""
        current_time = time.time()
        recent_events = [
            event for event in self.possession_events
            if current_time - event['timestamp'] <= time_window
        ]
        
        team_time = sum(event['duration'] for event in recent_events if event['team'] == team)
        total_time = sum(event['duration'] for event in recent_events)
        
        return (team_time / total_time * 100) if total_time > 0 else 0.0

class AdvancedAnalyticsDashboard:
    """Professional analytics dashboard widget"""
    
    def __init__(self, parent, stats_engine: RealTimeStatsEngine):
        self.parent = parent
        self.stats_engine = stats_engine
        self.heat_map_generator = HeatMapGenerator()
        self.possession_tracker = PossessionTracker()
        
        # UI elements
        self.notebook = None
        self.real_time_frame = None
        self.heat_map_frame = None
        self.analytics_frame = None
        
        self.create_dashboard()
        
        # Update timer
        self.update_dashboard()
    
    def create_dashboard(self):
        """Create the analytics dashboard UI"""
        # Main notebook for different analytics views
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Real-time stats tab
        self.real_time_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.real_time_frame, text="📊 Real-Time Stats")
        self.create_real_time_tab()
        
        # Heat maps tab
        self.heat_map_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.heat_map_frame, text="🔥 Heat Maps")
        self.create_heat_map_tab()
        
        # Advanced analytics tab
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text="📈 Analytics")
        self.create_analytics_tab()
    
    def create_real_time_tab(self):
        """Create real-time statistics tab"""
        # Team comparison section
        team_frame = ttk.LabelFrame(self.real_time_frame, text="Team Statistics", padding=10)
        team_frame.pack(fill='x', pady=5)
        
        # Player stats section
        player_frame = ttk.LabelFrame(self.real_time_frame, text="Player Leaders", padding=10)
        player_frame.pack(fill='both', expand=True, pady=5)
        
        # Create treeview for player stats
        columns = ('Name', 'Pos', 'G', 'A', 'P', 'S', 'S%', 'TOI')
        self.player_tree = ttk.Treeview(player_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.player_tree.heading(col, text=col)
            self.player_tree.column(col, width=80)
        
        scrollbar = ttk.Scrollbar(player_frame, orient='vertical', command=self.player_tree.yview)
        self.player_tree.configure(yscrollcommand=scrollbar.set)
        
        self.player_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    def create_heat_map_tab(self):
        """Create heat map visualization tab"""
        # Controls
        controls_frame = ttk.LabelFrame(self.heat_map_frame, text="Heat Map Controls", padding=10)
        controls_frame.pack(fill='x', pady=5)
        
        ttk.Label(controls_frame, text="Player:").pack(side='left')
        self.player_var = tk.StringVar(master=self)
        self.player_combo = ttk.Combobox(controls_frame, textvariable=self.player_var, width=20)
        self.player_combo.pack(side='left', padx=5)
        
        ttk.Label(controls_frame, text="Type:").pack(side='left', padx=(20, 0))
        self.heat_type_var = tk.StringVar(master=self, value="Position")
        heat_type_combo = ttk.Combobox(controls_frame, textvariable=self.heat_type_var, 
                                      values=["Position", "Shots"], width=15)
        heat_type_combo.pack(side='left', padx=5)
        
        generate_btn = ttk.Button(controls_frame, text="Generate Heat Map", 
                                 command=self.generate_heat_map)
        generate_btn.pack(side='left', padx=10)
        
        # Heat map display
        self.heat_map_canvas = tk.Canvas(self.heat_map_frame, bg='#16161a', height=400)
        self.heat_map_canvas.pack(fill='both', expand=True, pady=5)
    
    def create_analytics_tab(self):
        """Create advanced analytics tab"""
        # Momentum indicator
        momentum_frame = ttk.LabelFrame(self.analytics_frame, text="Game Momentum", padding=10)
        momentum_frame.pack(fill='x', pady=5)
        
        self.momentum_canvas = tk.Canvas(momentum_frame, height=100, bg='#16161a')
        self.momentum_canvas.pack(fill='x', pady=5)
        
        # Advanced metrics
        metrics_frame = ttk.LabelFrame(self.analytics_frame, text="Advanced Metrics", padding=10)
        metrics_frame.pack(fill='both', expand=True, pady=5)
        
        # Possession stats
        self.possession_label = ttk.Label(metrics_frame, text="Possession: Calculating...")
        self.possession_label.pack(anchor='w', pady=2)
        
        # Shooting efficiency
        self.efficiency_label = ttk.Label(metrics_frame, text="Shooting Efficiency: Calculating...")
        self.efficiency_label.pack(anchor='w', pady=2)
        
        # Zone time
        self.zone_time_label = ttk.Label(metrics_frame, text="Zone Time: Calculating...")
        self.zone_time_label.pack(anchor='w', pady=2)
    
    def generate_heat_map(self):
        """Generate and display heat map"""
        player_name = self.player_var.get()
        heat_type = self.heat_type_var.get()
        
        if not player_name:
            return
        
        # Find player
        player_stats = None
        for stats in self.stats_engine.player_stats.values():
            if stats.name == player_name:
                player_stats = stats
                break
        
        if not player_stats:
            return
        
        # Generate heat map
        if heat_type == "Position":
            heat_data = self.heat_map_generator.generate_player_heat_map(player_stats)
        else:  # Shots
            heat_data = self.heat_map_generator.generate_shot_heat_map(player_stats)
        
        # Visualize on canvas
        self.visualize_heat_map(heat_data)
    
    def visualize_heat_map(self, heat_data: List[List[float]]):
        """Visualize heat map data on canvas"""
        self.heat_map_canvas.delete("all")
        
        if not heat_data:
            return
        
        canvas_width = self.heat_map_canvas.winfo_width()
        canvas_height = self.heat_map_canvas.winfo_height()
        
        if canvas_width <= 1:  # Canvas not yet drawn
            self.parent.after(100, lambda: self.visualize_heat_map(heat_data))
            return
        
        rows = len(heat_data)
        cols = len(heat_data[0]) if rows > 0 else 0
        
        if rows == 0 or cols == 0:
            return
        
        cell_width = canvas_width / cols
        cell_height = canvas_height / rows
        
        for row in range(rows):
            for col in range(cols):
                intensity = heat_data[row][col]
                
                # Convert intensity to color (blue to red)
                if intensity > 0:
                    red = int(255 * intensity)
                    blue = int(255 * (1 - intensity))
                    color = f"#{red:02x}00{blue:02x}"
                    
                    x1 = col * cell_width
                    y1 = row * cell_height
                    x2 = x1 + cell_width
                    y2 = y1 + cell_height
                    
                    self.heat_map_canvas.create_rectangle(x1, y1, x2, y2, 
                                                         fill=color, outline="")
    
    def update_dashboard(self):
        """Update dashboard with latest statistics"""
        # Update player combo box
        player_names = [stats.name for stats in self.stats_engine.player_stats.values()]
        self.player_combo['values'] = player_names
        
        # Update player stats tree
        self.player_tree.delete(*self.player_tree.get_children())
        
        # Sort players by points
        sorted_players = sorted(self.stats_engine.player_stats.values(), 
                               key=lambda p: p.points, reverse=True)
        
        for player in sorted_players[:20]:  # Show top 20
            ice_time_formatted = f"{int(player.ice_time // 60)}:{int(player.ice_time % 60):02d}"
            self.player_tree.insert('', 'end', values=(
                player.name,
                player.position,
                player.goals,
                player.assists,
                player.points,
                player.shots,
                f"{player.shooting_percentage:.1f}%",
                ice_time_formatted
            ))
        
        # Update momentum visualization
        self.update_momentum_display()
        
        # Update advanced metrics
        self.update_advanced_metrics()
        
        # Schedule next update
        self.parent.after(1000, self.update_dashboard)  # Update every second
    
    def update_momentum_display(self):
        """Update momentum visualization"""
        self.momentum_canvas.delete("all")
        
        if len(self.stats_engine.team_stats) < 2:
            return
        
        teams = list(self.stats_engine.team_stats.keys())
        home_team = teams[0]
        away_team = teams[1]
        
        home_momentum = self.stats_engine.team_stats[home_team].momentum_score
        away_momentum = self.stats_engine.team_stats[away_team].momentum_score
        
        canvas_width = self.momentum_canvas.winfo_width()
        canvas_height = self.momentum_canvas.winfo_height()
        
        if canvas_width <= 1:
            return
        
        center_x = canvas_width / 2
        center_y = canvas_height / 2
        
        # Draw center line
        self.momentum_canvas.create_line(center_x, 0, center_x, canvas_height, 
                                        fill='black', width=2)
        
        # Draw momentum bars
        home_bar_width = abs(home_momentum) / 100 * (canvas_width / 2)
        away_bar_width = abs(away_momentum) / 100 * (canvas_width / 2)
        
        # Home team momentum (left side)
        if home_momentum != 0:
            color = '#4CAF50' if home_momentum > 0 else '#f85149'
            x1 = center_x - home_bar_width if home_momentum > 0 else center_x
            x2 = center_x if home_momentum > 0 else center_x - home_bar_width
            self.momentum_canvas.create_rectangle(x1, 10, x2, canvas_height - 10, 
                                                 fill=color, outline="")
        
        # Away team momentum (right side)  
        if away_momentum != 0:
            color = '#4CAF50' if away_momentum > 0 else '#f85149'
            x1 = center_x if away_momentum > 0 else center_x + away_bar_width
            x2 = center_x + away_bar_width if away_momentum > 0 else center_x
            self.momentum_canvas.create_rectangle(x1, 10, x2, canvas_height - 10, 
                                                 fill=color, outline="")
        
        # Team labels
        self.momentum_canvas.create_text(center_x / 2, center_y, text=home_team, 
                                        font=('Arial', 10, 'bold'))
        self.momentum_canvas.create_text(center_x + center_x / 2, center_y, text=away_team,
                                        font=('Arial', 10, 'bold'))
    
    def update_advanced_metrics(self):
        """Update advanced metrics display"""
        if len(self.stats_engine.team_stats) >= 2:
            teams = list(self.stats_engine.team_stats.keys())
            home_team = teams[0]
            away_team = teams[1]
            
            # Possession (placeholder - would be calculated from actual events)
            self.possession_label.config(text=f"Possession: {home_team} 52% - {away_team} 48%")
            
            # Shooting efficiency
            home_efficiency = self.stats_engine.team_stats[home_team].shooting_percentage
            away_efficiency = self.stats_engine.team_stats[away_team].shooting_percentage
            self.efficiency_label.config(
                text=f"Shooting %: {home_team} {home_efficiency:.1f}% - {away_team} {away_efficiency:.1f}%"
            )
            
            # Zone time (placeholder)
            self.zone_time_label.config(text="Zone Time: Offensive 35% - Neutral 40% - Defensive 25%")

# Test function
def test_advanced_analytics():
    """Test the advanced analytics system"""
    print("📊 Testing Advanced Statistics & Analytics System...")
    
    root = tk.Tk()
    root.title("Advanced Hockey Analytics Dashboard")
    root.geometry("1200x800")
    
    # Create stats engine
    stats_engine = RealTimeStatsEngine()
    
    # Initialize with sample data
    home_players = [
        {'id': 'H1', 'name': 'Connor McDavid', 'position': 'C'},
        {'id': 'H2', 'name': 'Leon Draisaitl', 'position': 'C'},
        {'id': 'H3', 'name': 'Zach Hyman', 'position': 'LW'},
    ]
    
    away_players = [
        {'id': 'A1', 'name': 'Auston Matthews', 'position': 'C'},
        {'id': 'A2', 'name': 'Mitch Marner', 'position': 'RW'},
        {'id': 'A3', 'name': 'William Nylander', 'position': 'RW'},
    ]
    
    stats_engine.initialize_game("Edmonton Oilers", "Toronto Maple Leafs", 
                                home_players, away_players)
    
    # Create dashboard
    dashboard = AdvancedAnalyticsDashboard(root, stats_engine)
    
    # Simulate some events
    def simulate_events():
        import random
        
        # Simulate random events
        events = [
            GameEvent(time.time(), "SHOT", "H1", "Edmonton Oilers", (800, 250), {"result": "SHOT"}),
            GameEvent(time.time() + 1, "GOAL", "A1", "Toronto Maple Leafs", (300, 250), {"result": "GOAL"}),
            GameEvent(time.time() + 2, "HIT", "H3", "Edmonton Oilers", (500, 200)),
        ]
        
        for event in events:
            stats_engine.process_event(event)
        
        # Schedule more events
        root.after(5000, simulate_events)
    
    # Start event simulation
    root.after(2000, simulate_events)
    
    root.mainloop()

if __name__ == "__main__":
    test_advanced_analytics()
