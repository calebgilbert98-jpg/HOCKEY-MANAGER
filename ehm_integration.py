"""
Integration Module for EHM-Style Simulation
Connects enhanced players with live game viewer
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from typing import List, Dict, Any
from ehm_simulation_engine import EHMSimulationEngine, GameAction, ActionType
from enhanced_player_system import EnhancedPlayer, PersonalityType
from game_classes import Player, PlayerPosition, Team
from position_specific_attributes import PlayerV2
from LIVE_GAME_VIEWER import LiveGameViewer
import random

class EHMGameIntegration:
    """Integration layer between EHM simulation and existing game systems"""
    
    def __init__(self, parent):
        self.parent = parent
        self.enhanced_players = {}  # Map regular players to enhanced players
        self.active_sim = None
        
    def convert_to_enhanced_player(self, regular_player) -> EnhancedPlayer:
        """Convert a regular Player or PlayerV2 to an EnhancedPlayer with personality"""
        
        # Check if already converted
        player_id = getattr(regular_player, 'id', f"{regular_player.first_name}_{regular_player.last_name}")
        if player_id in self.enhanced_players:
            return self.enhanced_players[player_id]
        
        # Determine player type and extract attributes accordingly
        if isinstance(regular_player, PlayerV2):
            # Handle PlayerV2 objects
            enhanced = self._convert_playerv2_to_enhanced(regular_player)
        else:
            # Handle regular Player objects
            enhanced = self._convert_player_to_enhanced(regular_player)
        
        # Store the mapping
        self.enhanced_players[player_id] = enhanced
        return enhanced
    
    def _convert_playerv2_to_enhanced(self, player: PlayerV2) -> EnhancedPlayer:
        """Convert PlayerV2 to EnhancedPlayer"""
        return EnhancedPlayer(
            id=str(player.id),
            first_name=player.first_name,
            last_name=player.last_name,
            age=player.age,
            primary_position=player.primary_position,
            overall=player.overall_rating(),
            
            # Convert PlayerV2 attributes to EnhancedPlayer attributes
            skating=max(5, (player.speed + player.acceleration + player.agility) // 3),
            shooting=max(5, (player.wristshot + player.slapshot + player.one_timer) // 3),
            passing=player.passing,
            checking=max(5, (player.checking + player.bodycheck + player.hitting) // 3),
            goaltending=player.reflexes if player.primary_position.value == 'G' else 10,
            
            # Enhanced technical attributes
            stickhandling=player.stickhandling,
            shooting_accuracy=player.wristshot,
            shooting_power=player.slapshot,
            passing_accuracy=player.passing,
            passing_vision=max(5, player.passing + random.randint(-3, 3)),
            skating_speed=player.speed,
            skating_agility=player.agility,
            body_checking=player.bodycheck,
            shot_blocking=player.shot_blocking,
            faceoffs=player.faceoffs,
            
            # Goalie attributes (if applicable)
            reflexes=player.reflexes if hasattr(player, 'reflexes') else random.randint(8, 15),
            positioning=player.positioning if hasattr(player, 'positioning') else random.randint(8, 15),
            rebound_control=player.rebound_control if hasattr(player, 'rebound_control') else random.randint(8, 15),
            glove_hand=player.glove_hand if hasattr(player, 'glove_hand') else random.randint(8, 15),
            blocker_hand=player.stick_side if hasattr(player, 'stick_side') else random.randint(8, 15),
            five_hole=random.randint(8, 15),
            
            # Physical attributes
            strength=player.strength,
            stamina=player.stamina,
            injury_resistance=random.randint(8, 16),
            size=random.randint(8, 18),
            reach=random.randint(8, 18),
            
            # Mental attributes based on PlayerV2 mental stats
            mental_toughness=player.composure,
            consistency=max(5, player.concentration + random.randint(-3, 3)),
            pressure_handling=player.composure,
            big_game_performance=max(5, player.bravery + random.randint(-3, 3)),
            clutch_factor=max(5, player.composure + player.bravery) // 2,
            focus=player.concentration,
            anticipation=player.anticipation,
            offensive_read=player.offensive_awareness,
            defensive_read=player.defensive_awareness,
            positioning_iq=max(5, player.anticipation + random.randint(-3, 3)),
            system_adaptability=random.randint(8, 16),
            
            # Personality attributes from PlayerV2
            leadership=player.leadership,
            teamwork=player.teamwork,
            selfishness=max(5, 20 - player.teamwork),  # Inverse of teamwork
            aggression=player.aggression,
            discipline=max(5, 20 - player.aggression),  # Inverse of aggression
            work_ethic=random.randint(12, 18),
            coachability=max(5, player.teamwork + random.randint(-3, 3)),
            
            # Situational attributes
            home_ice_comfort=random.randint(10, 18),
            travel_fatigue_resistance=max(5, player.stamina + random.randint(-5, 5)),
            rivalry_motivation=max(5, player.aggression + random.randint(-3, 3)),
            playoff_experience=random.randint(5, 15),
            
            # Assign personality type
            personality_type=self._determine_personality_type_v2(player)
        )
    
    def _convert_player_to_enhanced(self, player: Player) -> EnhancedPlayer:
        """Convert regular Player to EnhancedPlayer"""
        return EnhancedPlayer(
            id=player.id,
            first_name=player.first_name,
            last_name=player.last_name,
            age=player.age,
            primary_position=player.primary_position,
            overall=player.overall_rating(),
            
            # Convert basic attributes
            skating=player.skating,
            shooting=player.shooting,
            passing=player.passing,
            checking=player.checking,
            goaltending=player.goaltending,
            
            # Add enhanced attributes with intelligent defaults
            stickhandling=player.passing + random.randint(-3, 3),
            shooting_accuracy=player.shooting + random.randint(-5, 5),
            shooting_power=player.shooting + random.randint(-3, 3),
            passing_accuracy=player.passing + random.randint(-3, 3),
            passing_vision=player.passing + random.randint(-5, 5),
            body_checking=player.checking + random.randint(-3, 3),
            
            # Goalie attributes
            reflexes=player.goaltending + random.randint(-5, 5) if player.primary_position == PlayerPosition.GOALIE else random.randint(5, 15),
            positioning=player.goaltending + random.randint(-3, 3) if player.primary_position == PlayerPosition.GOALIE else random.randint(5, 15),
            rebound_control=player.goaltending + random.randint(-4, 4) if player.primary_position == PlayerPosition.GOALIE else random.randint(5, 15),
            
            # Skating attributes
            skating_speed=player.skating + random.randint(-3, 3),
            skating_agility=player.skating + random.randint(-3, 3),
            
            # Mental attributes based on overall rating
            mental_toughness=max(5, player.overall_rating() + random.randint(-8, 8)),
            consistency=max(5, player.overall_rating() + random.randint(-10, 10)),
            pressure_handling=max(5, player.overall_rating() + random.randint(-8, 8)),
            big_game_performance=max(5, player.overall_rating() + random.randint(-6, 6)),
            clutch_factor=max(5, player.overall_rating() + random.randint(-8, 8)),
            focus=max(5, player.overall_rating() + random.randint(-8, 8)),
            anticipation=max(5, player.overall_rating() + random.randint(-6, 6)),
            offensive_read=max(5, player.overall_rating() + random.randint(-8, 8)),
            defensive_read=max(5, player.overall_rating() + random.randint(-8, 8)),
            
            # Physical attributes
            strength=max(5, player.checking + random.randint(-5, 10)),
            stamina=random.randint(12, 18),
            injury_resistance=random.randint(8, 16),
            size=random.randint(8, 18),
            reach=random.randint(8, 18),
            
            # Personality attributes
            leadership=random.randint(8, 18) if player.overall_rating() > 44 else random.randint(5, 12),
            teamwork=random.randint(10, 18),
            selfishness=random.randint(5, 15),
            aggression=random.randint(8, 16),
            discipline=random.randint(10, 18),
            work_ethic=random.randint(12, 20),
            coachability=random.randint(10, 18),
            
            # Situational attributes
            home_ice_comfort=random.randint(10, 18),
            travel_fatigue_resistance=random.randint(8, 16),
            rivalry_motivation=random.randint(10, 18),
            playoff_experience=random.randint(5, 15),
            positioning_iq=max(5, player.overall_rating() + random.randint(-5, 5)),
            system_adaptability=random.randint(8, 16),
            
            # Assign personality type based on attributes
            personality_type=self._determine_personality_type(player)
        )
    
    def _determine_personality_type_v2(self, player: PlayerV2) -> PersonalityType:
        """Determine personality type based on PlayerV2 attributes"""
        overall = player.overall_rating()
        
        if overall >= 47:
            # Elite players
            if random.random() < 0.3:
                return PersonalityType.CLUTCH_PERFORMER
            elif random.random() < 0.2:
                return PersonalityType.VOLATILE_STAR
            else:
                return PersonalityType.STEADY_VETERAN
        elif overall >= 40:
            # Good players
            if random.random() < 0.4:
                return PersonalityType.STEADY_VETERAN
            elif random.random() < 0.3:
                return PersonalityType.CLUTCH_PERFORMER
            else:
                return PersonalityType.TEAM_PLAYER
        else:
            # Role players
            if random.random() < 0.5:
                return PersonalityType.CONSISTENT_GRINDER
            elif random.random() < 0.3:
                return PersonalityType.TEAM_PLAYER
            else:
                return PersonalityType.DEFENSIVE_SPECIALIST
    
    def _determine_personality_type(self, player: Player) -> PersonalityType:
        """Determine personality type based on player attributes"""
        if player.overall_rating() >= 47:
            # Elite players
            if random.random() < 0.3:
                return PersonalityType.CLUTCH_PERFORMER
            elif random.random() < 0.2:
                return PersonalityType.VOLATILE_STAR
            else:
                return PersonalityType.STEADY_VETERAN
        elif player.overall_rating() >= 40:
            # Good players
            if random.random() < 0.4:
                return PersonalityType.STEADY_VETERAN
            elif random.random() < 0.3:
                return PersonalityType.CLUTCH_PERFORMER
            else:
                return PersonalityType.TEAM_PLAYER
        else:
            # Role players
            if random.random() < 0.5:
                return PersonalityType.TEAM_PLAYER
            elif random.random() < 0.3:
                return PersonalityType.GRINDER
            else:
                return PersonalityType.INCONSISTENT_PROSPECT
    
    def launch_ehm_game_viewer(self, home_team: Team, away_team: Team):
        """Launch EHM-style game with enhanced simulation"""
        
        # Convert players to enhanced versions
        home_enhanced = [self.convert_to_enhanced_player(p) for p in home_team.roster]
        away_enhanced = [self.convert_to_enhanced_player(p) for p in away_team.roster]
        
        # Create EHM simulation engine
        self.active_sim = EHMSimulationEngine(
            home_team.team_name,
            away_team.team_name,
            home_enhanced,
            away_enhanced
        )
        
        # Launch specialized EHM viewer
        EHMGameViewer(self.parent, self.active_sim, home_team.team_name, away_team.team_name)

class EHMReplayViewer:
    """EHM-style game viewer for replay viewing"""
    
    def __init__(self, parent, home_team, away_team, event_log):
        self.parent = parent
        self.home_team = home_team.team_name if hasattr(home_team, 'team_name') else str(home_team)
        self.away_team = away_team.team_name if hasattr(away_team, 'team_name') else str(away_team)
        self.event_log = event_log
        
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title(f"🏒 EHM Replay: {self.home_team} vs {self.away_team}")
        self.window.configure(background='#181818')
        self.window.geometry("1400x900")
        
        # Replay control
        self.current_event = 0
        self.is_playing = False
        self.speed_multiplier = 1.0
        
        self._create_replay_interface()
        self._load_replay_data()
    
    def _create_replay_interface(self):
        """Create the EHM-style replay interface"""
        
        # Main container
        main_frame = tk.Frame(self.window, bg='#181818')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tk.Frame(main_frame, bg='#2A2A2A', height=60)
        header_frame.pack(fill='x', pady=(0, 10))
        header_frame.pack_propagate(False)
        
        # Game title
        title_label = tk.Label(header_frame, text=f"🏒 {self.home_team} vs {self.away_team}", 
                              font=('Segoe UI', 16, 'bold'), bg='#2A2A2A', fg='white')
        title_label.pack(side='left', padx=20, pady=15)
        
        # Replay controls
        controls_frame = tk.Frame(header_frame, bg='#2A2A2A')
        controls_frame.pack(side='right', padx=20, pady=10)
        
        tk.Button(controls_frame, text="⏮", font=('Segoe UI', 12), bg='#D13438', fg='white',
                 command=self._restart_replay, padx=10).pack(side='left', padx=2)
        
        tk.Button(controls_frame, text="⏸" if self.is_playing else "▶", font=('Segoe UI', 12), bg='#D13438', fg='white',
                 command=self._toggle_playback, padx=10).pack(side='left', padx=2)
        
        tk.Button(controls_frame, text="⏭", font=('Segoe UI', 12), bg='#D13438', fg='white',
                 command=self._skip_to_end, padx=10).pack(side='left', padx=2)
        
        # Content area
        content_frame = tk.Frame(main_frame, bg='#1F1F1F')
        content_frame.pack(fill='both', expand=True)
        
        # Event display
        tk.Label(content_frame, text="Game Replay", font=('Segoe UI', 14, 'bold'), 
                bg='#1F1F1F', fg='white').pack(pady=20)
        
        # Event log display
        self.event_text = tk.Text(content_frame, bg='#2A2A2A', fg='white', 
                                 font=('Consolas', 10), height=20, width=100)
        self.event_text.pack(padx=20, pady=10, fill='both', expand=True)
        
        # Status bar
        self.status_label = tk.Label(content_frame, text="Ready to play replay", 
                                    font=('Segoe UI', 10), bg='#1F1F1F', fg='#CCCCCC')
        self.status_label.pack(pady=10)
    
    def _load_replay_data(self):
        """Load and display replay data"""
        self.event_text.delete(1.0, tk.END)
        
        if not self.event_log:
            self.event_text.insert(tk.END, "No event log data available for this game.\n")
            return
            
        # Display event summary
        self.event_text.insert(tk.END, f"=== GAME REPLAY: {self.home_team} vs {self.away_team} ===\n\n")
        self.event_text.insert(tk.END, f"Total Events: {len(self.event_log)}\n\n")
        
        # Display first few events
        for i, event in enumerate(self.event_log[:20]):
            if isinstance(event, dict):
                event_type = event.get('type', 'UNKNOWN')
                timestamp = event.get('timestamp', 0)
                details = event.get('details', {})
                
                self.event_text.insert(tk.END, f"[{timestamp:.1f}s] {event_type}: {details}\n")
            else:
                self.event_text.insert(tk.END, f"Event {i}: {str(event)}\n")
        
        if len(self.event_log) > 20:
            self.event_text.insert(tk.END, f"\n... and {len(self.event_log) - 20} more events")
        
        self.status_label.config(text=f"Loaded {len(self.event_log)} events")
    
    def _toggle_playback(self):
        """Toggle replay playback"""
        self.is_playing = not self.is_playing
        # Implementation for actual playback would go here
        status = "Playing" if self.is_playing else "Paused"
        self.status_label.config(text=f"Replay {status}")
    
    def _restart_replay(self):
        """Restart replay from beginning"""
        self.current_event = 0
        self.status_label.config(text="Replay restarted")
    
    def _skip_to_end(self):
        """Skip to end of replay"""
        self.current_event = len(self.event_log) - 1
        self.status_label.config(text="Skipped to end")

class EHMGameViewer:
    """Specialized game viewer for EHM-style simulation"""
    
    def __init__(self, parent, simulation_engine: EHMSimulationEngine, home_team: str, away_team: str):
        self.parent = parent
        self.simulation_engine = simulation_engine
        self.home_team = home_team
        self.away_team = away_team
        
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title(f"🏒 EHM Live Game: {home_team} vs {away_team}")
        self.window.configure(background='#181818')
        self.window.geometry("1400x900")
        
        # Simulation control
        self.is_running = False
        self.simulation_thread = None
        self.speed_multiplier = 1.0
        
        # Event tracking
        self.recent_events = []
        self.max_recent_events = 50
        
        # Event storage for filtering
        self.all_events = []
        self.major_events = []
        
        self._create_interface()
        self._start_simulation()
    
    def _create_interface(self):
        """Create the EHM-style interface"""
        
        # Main container
        main_frame = tk.Frame(self.window, bg='#181818')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top section - Score and game info
        self._create_game_header(main_frame)
        
        # Middle section - Split between game state and events
        middle_frame = tk.Frame(main_frame, bg='#181818')
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Left side - Game state visualization
        self._create_game_state_panel(middle_frame)
        
        # Right side - Event log and analysis
        self._create_event_panel(middle_frame)
        
        # Bottom section - Controls and statistics
        self._create_control_panel(main_frame)
    
    def _create_game_header(self, parent):
        """Create the game header with score and time"""
        header_frame = tk.Frame(parent, bg='#2A2A2A', relief=tk.RAISED, bd=2)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Score display
        self.score_label = tk.Label(
            header_frame,
            text=f"{self.home_team} 0 - 0 {self.away_team}",
            font=('Segoe UI', 20, 'bold'),
            bg='#2A2A2A',
            fg='#FFFFFF'
        )
        self.score_label.pack(pady=10)
        
        # Game time and period
        time_frame = tk.Frame(header_frame, bg='#2A2A2A')
        time_frame.pack(pady=(0, 10))
        
        self.period_label = tk.Label(
            time_frame,
            text="Period 1",
            font=('Segoe UI', 14, 'bold'),
            bg='#2A2A2A',
            fg='#E0E0E0'
        )
        self.period_label.pack(side=tk.LEFT, padx=20)
        
        self.time_label = tk.Label(
            time_frame,
            text="20:00",
            font=('Segoe UI', 14, 'bold'),
            bg='#2A2A2A',
            fg='#E0E0E0'
        )
        self.time_label.pack(side=tk.LEFT, padx=20)
        
        self.momentum_label = tk.Label(
            time_frame,
            text="Momentum: Even",
            font=('Segoe UI', 12),
            bg='#2A2A2A',
            fg='#E0E0E0'
        )
        self.momentum_label.pack(side=tk.LEFT, padx=20)
    
    def _create_game_state_panel(self, parent):
        """Create game state visualization panel"""
        state_frame = tk.LabelFrame(
            parent,
            text="Game State",
            font=('Segoe UI', 12, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF',
            relief=tk.RAISED,
            bd=2
        )
        state_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Current situation
        self.situation_label = tk.Label(
            state_frame,
            text="Even Strength",
            font=('Segoe UI', 14, 'bold'),
            bg='#1F1F1F',
            fg='#D13438'
        )
        self.situation_label.pack(pady=10)
        
        # Possession info
        self.possession_label = tk.Label(
            state_frame,
            text=f"Possession: {self.home_team}",
            font=('Segoe UI', 12),
            bg='#1F1F1F',
            fg='#E0E0E0'
        )
        self.possession_label.pack(pady=5)
        
        # Zone info
        self.zone_label = tk.Label(
            state_frame,
            text="Zone: Neutral Zone",
            font=('Segoe UI', 12),
            bg='#1F1F1F',
            fg='#E0E0E0'
        )
        self.zone_label.pack(pady=5)
        
        # Players on ice
        self._create_players_on_ice_display(state_frame)
        
        # Momentum bar
        self._create_momentum_bar(state_frame)
    
    def _create_players_on_ice_display(self, parent):
        """Create display of current players on ice"""
        players_frame = tk.LabelFrame(
            parent,
            text="Players on Ice",
            font=('Segoe UI', 10, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF'
        )
        players_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Home team
        home_frame = tk.Frame(players_frame, bg='#1F1F1F')
        home_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            home_frame,
            text=f"{self.home_team}:",
            font=('Segoe UI', 9, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF'
        ).pack(anchor=tk.W)
        
        self.home_players_label = tk.Label(
            home_frame,
            text="Loading...",
            font=('Segoe UI', 8),
            bg='#1F1F1F',
            fg='#E0E0E0',
            wraplength=250
        )
        self.home_players_label.pack(anchor=tk.W, padx=10)
        
        # Away team
        away_frame = tk.Frame(players_frame, bg='#1F1F1F')
        away_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            away_frame,
            text=f"{self.away_team}:",
            font=('Segoe UI', 9, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF'
        ).pack(anchor=tk.W)
        
        self.away_players_label = tk.Label(
            away_frame,
            text="Loading...",
            font=('Segoe UI', 8),
            bg='#1F1F1F',
            fg='#E0E0E0',
            wraplength=250
        )
        self.away_players_label.pack(anchor=tk.W, padx=10)
    
    def _create_momentum_bar(self, parent):
        """Create momentum visualization"""
        momentum_frame = tk.LabelFrame(
            parent,
            text="Momentum",
            font=('Segoe UI', 10, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF'
        )
        momentum_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Momentum canvas
        self.momentum_canvas = tk.Canvas(
            momentum_frame,
            height=30,
            bg='#333333',
            highlightthickness=0
        )
        self.momentum_canvas.pack(fill=tk.X, padx=10, pady=5)
        
        # Initialize momentum display
        self._update_momentum_display(0)
    
    def _create_event_panel(self, parent):
        """Create event log and analysis panel"""
        event_frame = tk.LabelFrame(
            parent,
            text="Live Commentary & Events",
            font=('Segoe UI', 12, 'bold'),
            bg='#1F1F1F',
            fg='#FFFFFF',
            relief=tk.RAISED,
            bd=2
        )
        event_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Event filter controls
        filter_frame = tk.Frame(event_frame, bg='#1F1F1F')
        filter_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        tk.Label(
            filter_frame,
            text="Event Filter:",
            font=('Segoe UI', 9, 'bold'),
            bg='#1F1F1F',
            fg='#E0E0E0'
        ).pack(side=tk.LEFT)
        
        self.show_major_only = tk.BooleanVar(value=False)
        major_events_check = tk.Checkbutton(
            filter_frame,
            text="Major Events Only",
            variable=self.show_major_only,
            font=('Segoe UI', 9),
            bg='#1F1F1F',
            fg='#E0E0E0',
            selectcolor='#333333',
            activebackground='#1F1F1F',
            activeforeground='#E0E0E0',
            command=self._filter_events
        )
        major_events_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # Add separator
        separator = tk.Frame(filter_frame, height=1, bg='#444444')
        separator.pack(fill=tk.X, pady=(5, 0))
        
        # Event log with scrollbar
        log_frame = tk.Frame(event_frame, bg='#1F1F1F')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(log_frame, bg='#333333')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.event_log = tk.Text(
            log_frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=('Segoe UI', 9),
            bg='#2A2A2A',
            fg='#E0E0E0',
            insertbackground='#E0E0E0',
            selectbackground='#D13438',
            state=tk.DISABLED
        )
        self.event_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.event_log.yview)
        
        # Configure text tags for different event types with enhanced styling for major events
        self.event_log.tag_configure('goal', foreground='#00FF00', font=('Segoe UI', 11, 'bold'))
        self.event_log.tag_configure('save', foreground='#FFD700')
        self.event_log.tag_configure('penalty', foreground='#FF6B6B', font=('Segoe UI', 10, 'bold'))
        self.event_log.tag_configure('hit', foreground='#FF8C00', font=('Segoe UI', 10, 'bold'))
        self.event_log.tag_configure('fight', foreground='#FF0000', font=('Segoe UI', 11, 'bold'))
        self.event_log.tag_configure('injury', foreground='#FF69B4', font=('Segoe UI', 10, 'bold'))
        self.event_log.tag_configure('period', foreground='#87CEEB', font=('Segoe UI', 10, 'bold'))
        self.event_log.tag_configure('normal', foreground='#E0E0E0')
    
    def _create_control_panel(self, parent):
        """Create simulation control panel"""
        control_frame = tk.Frame(parent, bg='#2A2A2A', relief=tk.RAISED, bd=2)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Speed controls
        speed_frame = tk.Frame(control_frame, bg='#2A2A2A')
        speed_frame.pack(side=tk.LEFT, padx=20, pady=10)
        
        tk.Label(
            speed_frame,
            text="Speed:",
            font=('Segoe UI', 10, 'bold'),
            bg='#2A2A2A',
            fg='#E0E0E0'
        ).pack(side=tk.LEFT)
        
        self.speed_var = tk.StringVar(value="1x")
        speed_combo = ttk.Combobox(
            speed_frame,
            textvariable=self.speed_var,
            values=["0.5x", "1x", "2x", "5x", "10x"],
            width=8,
            state="readonly"
        )
        speed_combo.pack(side=tk.LEFT, padx=(10, 0))
        speed_combo.bind('<<ComboboxSelected>>', self._on_speed_change)
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg='#2A2A2A')
        button_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        
        self.pause_button = tk.Button(
            button_frame,
            text="⏸️ Pause",
            font=('Segoe UI', 10, 'bold'),
            bg='#D13438',
            fg='#FFFFFF',
            activebackground='#A1272A',
            command=self._toggle_pause,
            width=10
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="📊 Stats",
            font=('Segoe UI', 10, 'bold'),
            bg='#4A4A4A',
            fg='#FFFFFF',
            activebackground='#5A5A5A',
            command=self._show_detailed_stats,
            width=10
        ).pack(side=tk.LEFT, padx=5)
    
    def _start_simulation(self):
        """Start the simulation in a separate thread"""
        self.is_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.simulation_thread.start()
        
        # Start UI update loop
        self._update_ui()
    
    def _simulation_loop(self):
        """Main simulation loop"""
        while (self.is_running and 
               self.simulation_engine.game_state.period <= 3 and 
               self.simulation_engine.game_state.time_remaining > 0):
            
            if not self.is_running:
                break
            
            # Simulate next event
            action = self.simulation_engine.simulate_next_event()
            if not action:
                break
            
            # Add to recent events
            self.recent_events.append(action)
            if len(self.recent_events) > self.max_recent_events:
                self.recent_events.pop(0)
            
            # Sleep based on speed multiplier
            time.sleep(max(0.1, 2.0 / self.speed_multiplier))
            
            if 'game_end' in action.consequences:
                break
        
        # Game finished - save results
        self.is_running = False
        self._save_game_results()
    
    def _save_game_results(self):
        """Save simulation results back to the main game"""
        try:
            game_state = self.simulation_engine.game_state
            
            # Get the teams from the parent
            home_team = None
            away_team = None
            
            # Find the teams in the parent's game manager
            if hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'teams'):
                for team in self.parent.game_manager.teams:
                    if team.team_name == self.home_team:
                        home_team = team
                    elif team.team_name == self.away_team:
                        away_team = team
            
            if home_team and away_team:
                # Create game result object
                game_result = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': game_state.home_score,
                    'away_score': game_state.away_score,
                    'winner': home_team if game_state.home_score > game_state.away_score else away_team,
                    'loser': away_team if game_state.home_score > game_state.away_score else home_team,
                    'events': self.recent_events,
                    'major_events': self._extract_major_events(),
                    'game_stats': self._compile_game_stats()
                }
                
                # Save to parent's game results
                if not hasattr(self.parent, 'game_results'):
                    self.parent.game_results = []
                self.parent.game_results.append(game_result)
                
                # Update team records if applicable
                if hasattr(home_team, 'wins') and hasattr(home_team, 'losses'):
                    if game_state.home_score > game_state.away_score:
                        home_team.wins += 1
                        away_team.losses += 1
                    else:
                        away_team.wins += 1
                        home_team.losses += 1
                
                # Update any UI that might be listening
                if hasattr(self.parent, 'update_all_views'):
                    self.parent.update_all_views()
                
                print(f"Game result saved: {self.home_team} {game_state.home_score} - {game_state.away_score} {self.away_team}")
                
        except Exception as e:
            print(f"Error saving game results: {e}")
    
    def _extract_major_events(self):
        """Extract only major events from the recent events"""
        major_events = []
        for event in self.recent_events:
            is_major = False
            
            # Check for major events based on consequences and descriptions
            if 'goal_scored' in event.consequences:
                is_major = True
            elif 'penalty' in event.description.lower():
                is_major = True
            elif 'fight' in event.description.lower():
                is_major = True
            elif 'injur' in event.description.lower():
                is_major = True
            elif event.action_type == ActionType.CHECK and event.success and ('big' in event.description.lower() or 'hard' in event.description.lower()):
                is_major = True
            elif event.action_type == ActionType.SAVE and ('spectacular' in event.description.lower() or 'amazing' in event.description.lower()):
                is_major = True
            
            if is_major:
                major_events.append({
                    'type': event.action_type.value,
                    'description': event.description,
                    'player': event.primary_player.full_name if event.primary_player else 'Unknown',
                    'time': getattr(event, 'game_time', 'Unknown'),
                    'period': getattr(event, 'period', 'Unknown'),
                    'consequences': event.consequences
                })
        
        return major_events
    
    def _compile_game_stats(self):
        """Compile basic game statistics"""
        game_state = self.simulation_engine.game_state
        
        stats = {
            'final_score': f"{game_state.home_score} - {game_state.away_score}",
            'periods_played': game_state.period,
            'total_events': len(self.recent_events),
            'major_events_count': len(self._extract_major_events()),
            'momentum_final': game_state.momentum
        }
        
        return stats
    
    def _update_ui(self):
        """Update UI elements"""
        if not self.window.winfo_exists():
            return
        
        try:
            game_state = self.simulation_engine.game_state
            
            # Update score
            self.score_label.config(
                text=f"{self.home_team} {game_state.home_score} - {game_state.away_score} {self.away_team}"
            )
            
            # Update time and period
            minutes = int(game_state.time_remaining) // 60
            seconds = int(game_state.time_remaining) % 60
            self.time_label.config(text=f"{minutes:02d}:{seconds:02d}")
            self.period_label.config(text=f"Period {game_state.period}")
            
            # Update momentum
            momentum_text = self._get_momentum_text(game_state.momentum)
            self.momentum_label.config(text=f"Momentum: {momentum_text}")
            self._update_momentum_display(game_state.momentum)
            
            # Update possession and zone
            self.possession_label.config(text=f"Possession: {game_state.possession_team}")
            self.zone_label.config(text=f"Zone: {game_state.puck_location.zone.value.replace('_', ' ').title()}")
            
            # Update players on ice
            self._update_players_on_ice()
            
            # Update event log
            self._update_event_log()
            
        except Exception as e:
            print(f"UI Update error: {e}")
        
        # Schedule next update
        if self.is_running:
            self.window.after(500, self._update_ui)
    
    def _update_players_on_ice(self):
        """Update the players on ice display"""
        try:
            home_players = [f"{p.full_name} ({p.primary_position.value})" 
                           for p in self.simulation_engine.game_state.home_players_on_ice]
            away_players = [f"{p.full_name} ({p.primary_position.value})" 
                           for p in self.simulation_engine.game_state.away_players_on_ice]
            
            self.home_players_label.config(text=", ".join(home_players))
            self.away_players_label.config(text=", ".join(away_players))
        except:
            pass
    
    def _update_event_log(self):
        """Update the event log with recent events"""
        try:
            # Get new events since last update
            if hasattr(self, '_last_event_count'):
                new_events = self.recent_events[self._last_event_count:]
            else:
                new_events = self.recent_events[-5:]  # Show last 5 on startup
                self._last_event_count = 0
            
            # Add new events to log
            for event in new_events:
                self._add_event_to_log(event)
            
            self._last_event_count = len(self.recent_events)
        except Exception as e:
            print(f"Event log update error: {e}")
            import traceback
            traceback.print_exc()
    
    def _add_event_to_log(self, action: GameAction):
        """Add a single event to the log with appropriate formatting"""
        # Format timestamp
        total_time = int(1200 - self.simulation_engine.game_state.time_remaining)
        minutes = total_time // 60
        seconds = total_time % 60
        timestamp = f"[{minutes:02d}:{seconds:02d}] "
        
        # Determine if this is a major event and choose appropriate tag
        tag = 'normal'
        is_major_event = False
        
        # Check by ActionType first (more reliable)
        if hasattr(action, 'action_type'):
            if 'goal_scored' in action.consequences:
                tag = 'goal'
                is_major_event = True
            elif action.action_type == ActionType.CHECK and action.success:
                if 'big' in action.description.lower() or 'hard' in action.description.lower():
                    tag = 'hit'
                    is_major_event = True
            elif action.action_type == ActionType.SAVE:
                tag = 'save'
                # Major saves could be considered major events based on situation
                if 'spectacular' in action.description.lower() or 'amazing' in action.description.lower():
                    is_major_event = True
        else:
            # Fallback to description analysis
            if 'goal_scored' in action.consequences:
                tag = 'goal'
                is_major_event = True
            elif 'penalty' in action.description.lower() or 'penalt' in action.description.lower():
                tag = 'penalty'
                is_major_event = True
            elif 'fight' in action.description.lower() or 'scrum' in action.description.lower():
                tag = 'fight'
                is_major_event = True
            elif 'injur' in action.description.lower() or 'hurt' in action.description.lower():
                tag = 'injury'
                is_major_event = True
            elif 'save' in action.description.lower():
                tag = 'save'
        
        # Check for period/game end events
        if 'period_end' in action.consequences or 'game_end' in action.consequences:
            tag = 'period'
            is_major_event = True
        
        # Create event entry
        event_entry = {
            'timestamp': timestamp,
            'description': action.description,
            'tag': tag,
            'is_major': is_major_event
        }
        
        # Store event in appropriate lists
        self.all_events.append(event_entry)
        if is_major_event:
            self.major_events.append(event_entry)
        
        # Only display if passes current filter
        if not self.show_major_only.get() or is_major_event:
            self._display_event(event_entry)
    
    def _display_event(self, event_entry):
        """Display a single event in the log"""
        self.event_log.config(state=tk.NORMAL)
        
        # Add enhanced formatting for major events
        if event_entry['is_major']:
            self.event_log.insert(tk.END, "⭐ " + event_entry['timestamp'] + event_entry['description'] + " ⭐\n", event_entry['tag'])
        else:
            self.event_log.insert(tk.END, event_entry['timestamp'] + event_entry['description'] + "\n", event_entry['tag'])
        
        # Auto-scroll to bottom
        self.event_log.see(tk.END)
        self.event_log.config(state=tk.DISABLED)
    
    def _filter_events(self):
        """Filter events based on current filter settings"""
        self.event_log.config(state=tk.NORMAL)
        self.event_log.delete(1.0, tk.END)
        
        # Display events based on filter
        events_to_show = self.major_events if self.show_major_only.get() else self.all_events
        
        for event in events_to_show:
            self._display_event(event)
        
        self.event_log.config(state=tk.DISABLED)
    
    def _update_momentum_display(self, momentum: float):
        """Update the momentum bar visualization"""
        self.momentum_canvas.delete("all")
        width = self.momentum_canvas.winfo_width()
        if width <= 1:
            width = 300  # Default width
        
        height = 30
        center = width // 2
        
        # Draw background
        self.momentum_canvas.create_rectangle(0, 0, width, height, fill='#333333', outline='#555555')
        
        # Draw center line
        self.momentum_canvas.create_line(center, 0, center, height, fill='#FFFFFF', width=2)
        
        # Draw momentum bar
        momentum_width = abs(momentum) * (width // 2) / 100
        if momentum > 0:  # Home team momentum
            self.momentum_canvas.create_rectangle(
                center, 5, center + momentum_width, height - 5,
                fill='#00AA00', outline='#00DD00'
            )
        elif momentum < 0:  # Away team momentum
            self.momentum_canvas.create_rectangle(
                center - momentum_width, 5, center, height - 5,
                fill='#AA0000', outline='#DD0000'
            )
    
    def _get_momentum_text(self, momentum: float) -> str:
        """Convert momentum value to descriptive text"""
        if abs(momentum) < 10:
            return "Even"
        elif momentum > 0:
            if momentum > 50:
                return f"{self.home_team} Dominating"
            elif momentum > 25:
                return f"{self.home_team} Strong"
            else:
                return f"{self.home_team} Slight"
        else:
            if momentum < -50:
                return f"{self.away_team} Dominating"
            elif momentum < -25:
                return f"{self.away_team} Strong"
            else:
                return f"{self.away_team} Slight"
    
    def _toggle_pause(self):
        """Toggle simulation pause"""
        self.is_running = not self.is_running
        if self.is_running:
            self.pause_button.config(text="⏸️ Pause")
            # Restart simulation if needed
            if not self.simulation_thread.is_alive():
                self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
                self.simulation_thread.start()
            self._update_ui()
        else:
            self.pause_button.config(text="▶️ Play")
    
    def _on_speed_change(self, event):
        """Handle speed change"""
        speed_text = self.speed_var.get()
        try:
            self.speed_multiplier = float(speed_text.replace('x', ''))
        except:
            self.speed_multiplier = 1.0
    
    def _show_detailed_stats(self):
        """Show detailed game statistics"""
        stats_window = tk.Toplevel(self.window)
        stats_window.title("Game Statistics")
        stats_window.configure(bg='#181818')
        stats_window.geometry("800x600")
        
        # Create statistics display
        stats_text = tk.Text(
            stats_window,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='#2A2A2A',
            fg='#E0E0E0',
            state=tk.DISABLED
        )
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Populate with detailed statistics
        self._populate_detailed_stats(stats_text)
    
    def _populate_detailed_stats(self, text_widget):
        """Populate detailed statistics"""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        game_state = self.simulation_engine.game_state
        
        stats_text = f"""
GAME STATISTICS
===============

Final Score: {self.home_team} {game_state.home_score} - {game_state.away_score} {self.away_team}
Period: {game_state.period}
Time Remaining: {int(game_state.time_remaining) // 60:02d}:{int(game_state.time_remaining) % 60:02d}

MOMENTUM ANALYSIS
================
Current Momentum: {game_state.momentum:.1f}
{self._get_momentum_text(game_state.momentum)}

EVENT SUMMARY
=============
Total Events: {len(self.simulation_engine.event_log)}

Recent Events:
"""
        
        # Add recent events
        for i, event in enumerate(self.recent_events[-10:], 1):
            stats_text += f"{i:2d}. {event.description}\n"
        
        text_widget.insert(tk.END, stats_text)
        text_widget.config(state=tk.DISABLED)


# Add integration function to main application
def add_ehm_integration_to_main():
    """Integration function to add EHM capabilities to main application"""
    
    def launch_ehm_game(self):
        """Launch EHM-style game viewer"""
        if not hasattr(self, 'ehm_integration'):
            self.ehm_integration = EHMGameIntegration(self)
        
        # Get teams for the game
        if hasattr(self, 'game_manager') and self.game_manager.current_schedule:
            # Use scheduled game
            game = self.game_manager.current_schedule[0]  # Next game
            home_team = next(t for t in self.game_manager.teams if t.name == game['home_team'])
            away_team = next(t for t in self.game_manager.teams if t.name == game['away_team'])
        else:
            # Use default teams
            teams = list(self.game_manager.teams)
            home_team = teams[0]
            away_team = teams[1] if len(teams) > 1 else teams[0]
        
        self.ehm_integration.launch_ehm_game_viewer(home_team, away_team)
    
    return launch_ehm_game
