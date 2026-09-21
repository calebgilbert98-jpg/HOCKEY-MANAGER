"""
Enhanced Practice-Based Player Development System
Gradual skill improvement through focused training sessions
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple
from datetime import date, timedelta
from dataclasses import dataclass, field
from enum import Enum
import random
import json


class PracticeType(Enum):
    """Types of practice sessions available"""
    SKATING = "skating"
    SHOOTING = "shooting"
    PASSING = "passing"
    CHECKING = "checking"
    DEFENSE = "defense"
    FACEOFFS = "faceoffs"
    CONDITIONING = "conditioning"
    HOCKEY_IQ = "hockey_iq"
    TEAMWORK = "teamwork"
    LEADERSHIP = "leadership"


class PracticeIntensity(Enum):
    """Practice intensity levels"""
    LIGHT = "light"
    MODERATE = "moderate"
    INTENSE = "intense"
    EXTREME = "extreme"


@dataclass
@dataclass
class PracticeSession:
    """Individual practice session"""
    practice_type: PracticeType
    intensity: PracticeIntensity
    duration_minutes: int
    trainer_quality: int  # 1-20 scale
    date_completed: date
    skill_gain: float  # Actual skill points gained
    fatigue_cost: int  # Fatigue added to player

@dataclass
class PracticeResult:
    """Result of a practice session or scheduling operation"""
    success: bool
    message: str
    improvement: float = 0.0
    fatigue_increase: int = 0

@dataclass
class PlayerPracticeHistory:
    """Track a player's practice history"""
    player_id: str
    total_sessions: int = 0
    sessions_by_type: Dict[PracticeType, int] = field(default_factory=dict)
    recent_sessions: List[PracticeSession] = field(default_factory=list)
    total_skill_gains: Dict[str, float] = field(default_factory=dict)
    current_fatigue: int = 0  # 0-100 scale
    last_practice_date: Optional[date] = None
    current_schedule: Optional[Dict] = None  # For scheduled practice sessions
    
    def add_session(self, session: PracticeSession):
        """Add a completed practice session"""
        self.total_sessions += 1
        self.sessions_by_type[session.practice_type] = self.sessions_by_type.get(session.practice_type, 0) + 1
        self.recent_sessions.append(session)
        self.current_fatigue = min(100, self.current_fatigue + session.fatigue_cost)
        self.last_practice_date = session.date_completed
        
        # Keep only last 50 sessions for memory efficiency
        if len(self.recent_sessions) > 50:
            self.recent_sessions = self.recent_sessions[-50:]


class PracticeEngine:
    """Enhanced practice-based development engine"""
    
    def __init__(self):
        self.player_histories: Dict[str, PlayerPracticeHistory] = {}
        self.practice_effectiveness = self._initialize_effectiveness_map()
        self.fatigue_recovery_rate = 2  # Points per day
        
    def _initialize_effectiveness_map(self) -> Dict[PracticeType, Dict[str, float]]:
        """Map practice types to attribute improvements"""
        return {
            PracticeType.SKATING: {
                'skating': 1.0, 'speed': 0.8, 'acceleration': 0.8, 'agility': 0.6,
                'balance': 0.4, 'stamina': 0.3
            },
            PracticeType.SHOOTING: {
                'shooting': 1.0, 'shooting_accuracy': 0.9, 'shooting_power': 0.8,
                'wrist_shot': 0.7, 'slap_shot': 0.7, 'composure': 0.3
            },
            PracticeType.PASSING: {
                'passing': 1.0, 'passing_accuracy': 0.9, 'passing_creativity': 0.8,
                'vision': 0.6, 'hockey_iq': 0.4, 'anticipation': 0.3
            },
            PracticeType.CHECKING: {
                'checking': 1.0, 'strength': 0.8, 'aggressiveness': 0.7,
                'body_checking': 0.9, 'balance': 0.5, 'intimidation': 0.4
            },
            PracticeType.DEFENSE: {
                'defense': 1.0, 'defensive_awareness': 0.9, 'pokecheck': 0.8,
                'stick_checking': 0.8, 'shot_blocking': 0.6, 'anticipation': 0.5
            },
            PracticeType.FACEOFFS: {
                'faceoffs': 1.0, 'anticipation': 0.6, 'strength': 0.4,
                'hockey_iq': 0.3, 'determination': 0.3
            },
            PracticeType.CONDITIONING: {
                'stamina': 1.0, 'strength': 0.7, 'speed': 0.5,
                'acceleration': 0.4, 'durability': 0.6
            },
            PracticeType.HOCKEY_IQ: {
                'hockey_iq': 1.0, 'vision': 0.8, 'anticipation': 0.8,
                'defensive_awareness': 0.6, 'positioning': 0.7
            },
            PracticeType.TEAMWORK: {
                'teamwork': 1.0, 'leadership': 0.6, 'discipline': 0.5,
                'passing': 0.3, 'defensive_awareness': 0.4
            },
            PracticeType.LEADERSHIP: {
                'leadership': 1.0, 'determination': 0.8, 'composure': 0.7,
                'teamwork': 0.6, 'discipline': 0.5
            }
        }
    
    def get_player_history(self, player_id: str) -> PlayerPracticeHistory:
        """Get or create practice history for a player"""
        if player_id not in self.player_histories:
            self.player_histories[player_id] = PlayerPracticeHistory(player_id)
        return self.player_histories[player_id]
    
    def can_practice(self, player, practice_type: PracticeType, intensity: PracticeIntensity) -> Tuple[bool, str]:
        """Check if player can do this practice session"""
        history = self.get_player_history(player.id)
        
        # Check fatigue
        fatigue_cost = self._calculate_fatigue_cost(intensity, 60)  # 60 min default
        if history.current_fatigue + fatigue_cost > 95:
            return False, f"Player too fatigued ({history.current_fatigue}/100). Rest needed."
        
        # Check if practiced same type today
        if (history.last_practice_date == date.today() and 
            intensity in [PracticeIntensity.INTENSE, PracticeIntensity.EXTREME]):
            return False, "Player already had intense practice today."
        
        # Check injury status (if implemented)
        if hasattr(player, 'injury_status') and player.injury_status != "Healthy":
            return False, f"Player injured: {player.injury_status}"
        
        return True, "Ready to practice"
    
    def execute_practice(self, player, practice_type: PracticeType, 
                        intensity: PracticeIntensity, duration_minutes: int = 60,
                        trainer_quality: int = 10) -> PracticeSession:
        """Execute a practice session and apply improvements"""
        
        # Calculate base effectiveness
        base_effectiveness = self._calculate_base_effectiveness(
            player, practice_type, intensity, duration_minutes, trainer_quality
        )
        
        # Apply improvements to relevant attributes
        skill_gains = {}
        practice_map = self.practice_effectiveness[practice_type]
        
        for attribute, multiplier in practice_map.items():
            if hasattr(player, attribute):
                current_value = getattr(player, attribute)
                
                # Calculate improvement with diminishing returns
                improvement = self._calculate_skill_improvement(
                    current_value, base_effectiveness * multiplier, player.age
                )
                
                if improvement > 0:
                    new_value = min(20, current_value + improvement)
                    setattr(player, attribute, new_value)
                    skill_gains[attribute] = improvement
        
        # Calculate fatigue cost
        fatigue_cost = self._calculate_fatigue_cost(intensity, duration_minutes)
        
        # Create session record
        session = PracticeSession(
            practice_type=practice_type,
            intensity=intensity,
            duration_minutes=duration_minutes,
            trainer_quality=trainer_quality,
            date_completed=date.today(),
            skill_gain=sum(skill_gains.values()),
            fatigue_cost=fatigue_cost
        )
        
        # Update player history
        history = self.get_player_history(player.id)
        history.add_session(session)
        
        return session
    
    def _calculate_base_effectiveness(self, player, practice_type: PracticeType,
                                   intensity: PracticeIntensity, duration: int, 
                                   trainer_quality: int) -> float:
        """Calculate base practice effectiveness"""
        
        # Intensity multipliers
        intensity_mult = {
            PracticeIntensity.LIGHT: 0.5,
            PracticeIntensity.MODERATE: 1.0,
            PracticeIntensity.INTENSE: 1.5,
            PracticeIntensity.EXTREME: 2.0
        }
        
        # Duration effect (diminishing returns after 60 minutes)
        duration_mult = min(1.5, duration / 60)
        if duration > 60:
            duration_mult = 1.0 + (duration - 60) / 120  # Slower gains past 60 min
        
        # Trainer quality (1-20 scale)
        trainer_mult = 0.5 + (trainer_quality / 20) * 0.8  # 0.5 to 1.3 range
        
        # Player age factor (younger players learn faster)
        age_mult = self._get_age_multiplier(player.age)
        
        # Player work ethic (if available)
        work_ethic_mult = 1.0
        if hasattr(player, 'work_rate'):
            work_ethic_mult = 0.7 + (player.work_rate / 20) * 0.6
        
        # Random factor for realism
        random_mult = random.uniform(0.8, 1.2)
        
        base_effectiveness = (intensity_mult[intensity] * duration_mult * 
                            trainer_mult * age_mult * work_ethic_mult * random_mult)
        
        return base_effectiveness * 0.1  # Scale to reasonable improvement levels
    
    def _calculate_skill_improvement(self, current_value: int, effectiveness: float, age: int) -> float:
        """Calculate actual skill point improvement with diminishing returns"""
        
        # Diminishing returns - harder to improve high attributes
        if current_value >= 18:
            effectiveness *= 0.2
        elif current_value >= 15:
            effectiveness *= 0.5
        elif current_value >= 12:
            effectiveness *= 0.8
        
        # Age factor for skill retention
        if age > 30:
            effectiveness *= 0.8
        elif age > 35:
            effectiveness *= 0.6
        
        return max(0, min(1.0, effectiveness))  # Cap at 1 point per session
    
    def _calculate_fatigue_cost(self, intensity: PracticeIntensity, duration: int) -> int:
        """Calculate fatigue cost of practice session"""
        
        intensity_cost = {
            PracticeIntensity.LIGHT: 5,
            PracticeIntensity.MODERATE: 10,
            PracticeIntensity.INTENSE: 20,
            PracticeIntensity.EXTREME: 35
        }
        
        base_cost = intensity_cost[intensity]
        duration_mult = duration / 60  # Scale by duration
        
        return int(base_cost * duration_mult)
    
    def _get_age_multiplier(self, age: int) -> float:
        """Get age-based learning multiplier"""
        if age <= 20:
            return 1.4
        elif age <= 25:
            return 1.2
        elif age <= 30:
            return 1.0
        elif age <= 35:
            return 0.8
        else:
            return 0.6
    
    def recover_fatigue(self, player_id: str, days: int = 1):
        """Recover fatigue over time"""
        history = self.get_player_history(player_id)
        recovery = self.fatigue_recovery_rate * days
        history.current_fatigue = max(0, history.current_fatigue - recovery)
    
    def get_practice_recommendations(self, player) -> List[Tuple[PracticeType, str]]:
        """Get recommended practice types for a player"""
        recommendations = []
        
        # Analyze player's weak areas
        attributes = {
            'skating': getattr(player, 'skating', 10),
            'shooting': getattr(player, 'shooting', 10),
            'passing': getattr(player, 'passing', 10),
            'checking': getattr(player, 'checking', 10),
            'defense': getattr(player, 'defense', 10),
            'faceoffs': getattr(player, 'faceoffs', 10),
        }
        
        # Sort by lowest values (areas that need work)
        sorted_attrs = sorted(attributes.items(), key=lambda x: x[1])
        
        practice_mapping = {
            'skating': (PracticeType.SKATING, "Improve speed and agility"),
            'shooting': (PracticeType.SHOOTING, "Develop scoring ability"),
            'passing': (PracticeType.PASSING, "Enhance playmaking skills"),
            'checking': (PracticeType.CHECKING, "Build physical presence"),
            'defense': (PracticeType.DEFENSE, "Strengthen defensive play"),
            'faceoffs': (PracticeType.FACEOFFS, "Improve faceoff percentage")
        }
        
        # Recommend top 3 weakest areas
        for attr_name, value in sorted_attrs[:3]:
            if attr_name in practice_mapping and value < 15:
                practice_type, reason = practice_mapping[attr_name]
                recommendations.append((practice_type, f"{reason} (Current: {value})"))
        
        # Add leadership/teamwork for older players
        if player.age >= 25:
            leadership_val = getattr(player, 'leadership', 10)
            if leadership_val < 15:
                recommendations.append((PracticeType.LEADERSHIP, "Develop leadership qualities"))
        
        return recommendations
    
    def schedule_practice(self, player, practice_type: PracticeType, intensity: PracticeIntensity, total_sessions: int):
        """Schedule a practice regimen for a player"""
        try:
            history = self.get_player_history(player.id)
            
            # Check if player is too fatigued
            if history.current_fatigue > 80:
                return PracticeResult(
                    success=False,
                    message=f"{player.full_name} is too fatigued for practice (Fatigue: {history.current_fatigue}%)"
                )
            
            # Set up schedule
            history.current_schedule = {
                'type': practice_type,
                'intensity': intensity,
                'sessions_remaining': total_sessions,
                'total_sessions': total_sessions
            }
            
            return PracticeResult(
                success=True,
                message=f"Practice schedule set for {player.full_name}",
                improvement=0.0,
                fatigue_increase=0
            )
            
        except Exception as e:
            return PracticeResult(
                success=False,
                message=f"Error scheduling practice: {str(e)}"
            )
    
    def stop_practice_schedule(self, player):
        """Stop current practice schedule for a player"""
        history = self.get_player_history(player.id)
        history.current_schedule = None
    
    def process_scheduled_practices(self):
        """Process all scheduled practices (called during game simulation)"""
        # This would be called during time advancement in the game
        for player_id, history in self.player_histories.items():
            if history.current_schedule and history.current_schedule['sessions_remaining'] > 0:
                # Find player object (this would need to be implemented based on game structure)
                # For now, just decrement sessions
                history.current_schedule['sessions_remaining'] -= 1
                if history.current_schedule['sessions_remaining'] <= 0:
                    history.current_schedule = None


class DevelopmentOverviewWindow(tk.Toplevel):
    """Development overview window showing all team players"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Development Overview & Progress")
        self.configure(background=parent.BG_COLOR)
        self.geometry("1200x800")
        
        # Initialize practice engine
        if not hasattr(parent, 'practice_engine'):
            parent.practice_engine = PracticeEngine()
        
        self.practice_engine = parent.practice_engine
        self.selected_player = None
        
        self._create_interface()
        self._populate_players()
        
        # Track window for lifecycle management
        self.parent.open_windows['development_overview'] = self
    
    def _create_interface(self):
        """Create the enhanced development overview interface"""
        # Main container with zero padding to maximize usable area
        main_container = ttk.Frame(self, style='Content.TFrame')
        main_container.pack(fill='both', expand=True, padx=0, pady=0)
        
        # Top section - Quick actions - more compact
        top_frame = ttk.Frame(main_container, style='Content.TFrame')
        top_frame.pack(fill='x', pady=(0, 3))
        
        # Title
        title_label = ttk.Label(top_frame, text="🏒 Player Development Center", 
                               style='Title.TLabel', font=(self.parent.FONT_FAMILY, 24, 'bold'))  # Increased from 18 to 24
        title_label.pack(side='left')
        
        # Quick action buttons
        actions_frame = ttk.Frame(top_frame, style='Content.TFrame')
        actions_frame.pack(side='right')
        
        ttk.Button(actions_frame, text="🏋️ Practice Center", 
                  command=self._open_practice_window, style='Accent.TButton').pack(side='right', padx=(5, 0))
        
        ttk.Button(actions_frame, text="📊 Team Analysis", 
                  command=self._show_team_analysis, style='TButton').pack(side='right', padx=(5, 0))
        
        # Main content area with flexible grid layout
        content_container = ttk.Frame(main_container, style='Content.TFrame')
        content_container.pack(fill='both', expand=True)
        
        # Configure grid for aggressive space allocation - left panel should be narrower
        content_container.grid_columnconfigure(0, weight=25, minsize=250)  # Player list column - reduced from 300
        content_container.grid_columnconfigure(1, weight=75)  # Player details column - increased weight
        content_container.grid_rowconfigure(0, weight=1)
        
        # Left side - Player list (25% weight, minimum 250px)
        left_frame = ttk.LabelFrame(content_container, text="🏒 Team Roster", style='Card.TLabelframe')
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        # Configure the left frame to expand its content
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Player list
        self._create_player_list(left_frame)
        
        # Right side - Player details (75% weight)
        right_frame = ttk.LabelFrame(content_container, text="📊 Player Development Details", 
                                    style='Card.TLabelframe')
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(2, 0))
        # Configure the right frame to expand its content
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Player info display
        self._create_player_details(right_frame)
        
        # Bottom status bar with zero spacing
        status_frame = ttk.Frame(main_container, style='Content.TFrame')
        status_frame.pack(fill='x', pady=(3, 0))
        
        self.status_bar = ttk.Label(status_frame, text="Select a player to view development details", 
                                   style='Content.TLabel', font=(self.parent.FONT_FAMILY, 14))  # Increased from 10 to 14
        self.status_bar.pack(side='left')
        
        # Bottom right - Close button
        ttk.Button(status_frame, text="❌ Close", 
                  command=self.destroy, style='TButton').pack(side='right')
    
    def _create_player_list(self, parent):
        """Create enhanced player selection list"""
        # Configure parent to expand content
        parent.grid_rowconfigure(1, weight=1)  # Row 1 will contain the treeview
        parent.grid_columnconfigure(0, weight=1)  # Column 0 for treeview (expands)
        parent.grid_columnconfigure(1, weight=0)  # Column 1 for scrollbar (fixed)
        
        # Filter and sort options with zero padding
        filter_frame = ttk.Frame(parent, style='Content.TFrame')
        filter_frame.grid(row=0, column=0, sticky='ew', padx=2, pady=(2, 1))
        
        # Filter by roster type
        ttk.Label(filter_frame, text="Filter:", style='Content.TLabel').pack(side='left')
        
        self.filter_var = tk.StringVar(value="All Players")
        filter_options = ["All Players", "NHL Roster", "AHL Roster", "Prospects", "Under 25", "Needs Development"]
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                  values=filter_options, state='readonly', width=15)
        filter_combo.configure(foreground='black')
        filter_combo.pack(side='left', padx=(5, 0))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self._populate_players())
        
        # Sort options
        ttk.Label(filter_frame, text="Sort:", style='Content.TLabel').pack(side='left', padx=(10, 0))
        
        self.sort_var = tk.StringVar(value="Name")
        sort_options = ["Name", "Age", "Overall", "Position", "Status", "Last Practice"]
        sort_combo = ttk.Combobox(filter_frame, textvariable=self.sort_var,
                                values=sort_options, state='readonly', width=12)
        sort_combo.configure(foreground='black')
        sort_combo.pack(side='left', padx=(5, 0))
        sort_combo.bind('<<ComboboxSelected>>', lambda e: self._populate_players())
        
        # Player treeview with enhanced columns
        columns = {
            'name': ('Player', 140),
            'pos': ('Pos', 45),
            'age': ('Age', 40),
            'overall': ('Overall', 60),
            'potential': ('Potential', 70),
            'fatigue': ('Fatigue', 60),
            'sessions': ('Sessions', 60),
            'status': ('Status', 70)
        }
        
        self.player_tree = ttk.Treeview(parent, columns=list(columns.keys()), 
                                       show='headings')  # Remove fixed height to allow expansion
        
        for col_id, (header, width) in columns.items():
            self.player_tree.heading(col_id, text=header)
            self.player_tree.column(col_id, width=width, anchor='center')
        
        # Enhanced styling for different player types
        self.player_tree.tag_configure('nhl_player', background='#2d4a2d')  # Dark green
        self.player_tree.tag_configure('ahl_player', background='#3d3d2d')  # Dark yellow
        self.player_tree.tag_configure('prospect', background='#2d2d4a')    # Dark blue
        self.player_tree.tag_configure('young_star', background='#4a2d4a')  # Dark purple
        self.player_tree.tag_configure('veteran', background='#4a3d2d')     # Dark brown
        
        # Scrollbar
        player_scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.player_tree.yview)
        self.player_tree.configure(yscrollcommand=player_scrollbar.set)
        
        # Use grid for proper expansion within the LabelFrame
        self.player_tree.grid(row=1, column=0, sticky='nsew', padx=(2, 0), pady=(0, 2))
        player_scrollbar.grid(row=1, column=1, sticky='ns', pady=(0, 2))
        
        # Bind selection with enhanced feedback
        self.player_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        self.player_tree.bind('<Double-1>', self._on_player_double_click)
    
    def _create_player_details(self, parent):
        """Create comprehensive player details display"""
        # Configure parent for grid expansion
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=0)
        
        # Scrollable frame for player details
        canvas = tk.Canvas(parent, bg=self.parent.CONTENT_BG)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.details_frame = ttk.Frame(canvas, style='Content.TFrame')
        
        self.details_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.details_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Use grid for proper expansion
        canvas.grid(row=0, column=0, sticky='nsew', padx=(2, 0), pady=2)
        scrollbar.grid(row=0, column=1, sticky='ns', pady=2)
        
        # Default message
        self.default_label = ttk.Label(self.details_frame, 
                                     text="Select a player to view detailed development information",
                                     style='Content.TLabel', font=(self.parent.FONT_FAMILY, 16))  # Increased from 12 to 16
        self.default_label.pack(pady=50)
    
    def _open_practice_window(self):
        """Open the practice center for active roster players"""
        if 'practice_center' not in self.parent.open_windows or not self.parent.open_windows['practice_center'].winfo_exists():
            self.parent.open_windows['practice_center'] = PracticeCenterWindow(self.parent)
        self.parent.open_windows['practice_center'].focus_set()
    
    def _show_team_analysis(self):
        """Show comprehensive team development analysis"""
        # Check if we have access to user team data
        user_team = None
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            user_team = self.parent.user_team
        elif hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
            user_team = self.parent.game_manager.user_team
        else:
            messagebox.showwarning("No Team", "No team data available")
            return
        
        # Gather team statistics
        all_players = (user_team.roster + 
                      user_team.ahl_roster + 
                      user_team.prospects)
        
        if not all_players:
            messagebox.showinfo("Team Analysis", "No players found in the organization")
            return
        
        # Age analysis
        young_players = [p for p in all_players if p.age <= 23]
        prime_players = [p for p in all_players if 24 <= p.age <= 29]
        veteran_players = [p for p in all_players if p.age >= 30]
        
        # Overall rating analysis
        total_players = len(all_players)
        avg_overall = sum(p.overall_rating() for p in all_players) / total_players
        
        elite_players = [p for p in all_players if p.overall_rating() >= 16]
        good_players = [p for p in all_players if 13 <= p.overall_rating() < 16]
        developing_players = [p for p in all_players if p.overall_rating() < 13]
        
        # Practice analysis
        active_practitioners = []
        total_sessions = 0
        
        for player in all_players:
            history = self.practice_engine.get_player_history(player.id)
            if history.total_sessions > 0:
                active_practitioners.append(player)
                total_sessions += history.total_sessions
        
        # Generate analysis report
        analysis_text = f"🏒 TEAM DEVELOPMENT ANALYSIS\n"
        analysis_text += f"{'='*50}\n\n"
        
        analysis_text += f"📊 ROSTER COMPOSITION:\n"
        analysis_text += f"Total Players: {total_players}\n"
        analysis_text += f"NHL Roster: {len(user_team.roster)}\n"
        analysis_text += f"AHL Roster: {len(user_team.ahl_roster)}\n"
        analysis_text += f"Prospects: {len(user_team.prospects)}\n\n"
        
        analysis_text += f"👥 AGE DISTRIBUTION:\n"
        analysis_text += f"Young Players (≤23): {len(young_players)} ({len(young_players)/total_players*100:.1f}%)\n"
        analysis_text += f"Prime Players (24-29): {len(prime_players)} ({len(prime_players)/total_players*100:.1f}%)\n"
        analysis_text += f"Veterans (30+): {len(veteran_players)} ({len(veteran_players)/total_players*100:.1f}%)\n\n"
        
        analysis_text += f"⭐ SKILL LEVELS:\n"
        analysis_text += f"Average Overall Rating: {avg_overall:.1f}\n"
        analysis_text += f"Elite Players (16+): {len(elite_players)} ({len(elite_players)/total_players*100:.1f}%)\n"
        analysis_text += f"Good Players (13-15): {len(good_players)} ({len(good_players)/total_players*100:.1f}%)\n"
        analysis_text += f"Developing Players (<13): {len(developing_players)} ({len(developing_players)/total_players*100:.1f}%)\n\n"
        
        analysis_text += f"🏋️ TRAINING ACTIVITY:\n"
        analysis_text += f"Active Practitioners: {len(active_practitioners)}/{total_players}\n"
        analysis_text += f"Total Practice Sessions: {total_sessions}\n"
        
        if active_practitioners:
            avg_sessions = total_sessions / len(active_practitioners)
            analysis_text += f"Average Sessions per Active Player: {avg_sessions:.1f}\n"
        
        analysis_text += f"\n💡 RECOMMENDATIONS:\n"
        
        if len(young_players) / total_players > 0.4:
            analysis_text += "• High number of young players - Focus on fundamental skill development\n"
        
        if len(developing_players) / total_players > 0.3:
            analysis_text += "• Many developing players - Implement structured training programs\n"
        
        if len(active_practitioners) / total_players < 0.5:
            analysis_text += "• Low training participation - Encourage more practice sessions\n"
        
        if avg_overall < 12:
            analysis_text += "• Below-average skill levels - Prioritize intensive development\n"
        
        if len(veteran_players) / total_players > 0.3:
            analysis_text += "• Veteran-heavy roster - Focus on mentorship and leadership development\n"
        
        # Show analysis in a scrollable dialog
        analysis_window = tk.Toplevel(self)
        analysis_window.title("Team Development Analysis")
        analysis_window.configure(background=self.parent.BG_COLOR)
        analysis_window.geometry("600x500")
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(analysis_window, style='Content.TFrame')
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        text_widget = tk.Text(text_frame, wrap='word', font=(self.parent.FONT_FAMILY, 14),  # Increased from 10 to 14
                             bg=self.parent.CONTENT_BG, fg=self.parent.TEXT_COLOR)
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        text_widget.insert('1.0', analysis_text)
        text_widget.configure(state='disabled')
        
        # Close button
        ttk.Button(analysis_window, text="Close", command=analysis_window.destroy,
                  style='TButton').pack(pady=(0, 20))
    
    def _view_progress(self):
        """View development progress charts"""
        if not self.selected_player:
            messagebox.showwarning("No Player", "Please select a player first")
            return
        
        # Show development progress for selected player
        history = self.practice_engine.get_player_history(self.selected_player.id)
        
        progress_text = f"Development Progress for {self.selected_player.full_name}:\n\n"
        progress_text += f"Total Practice Sessions: {history.total_sessions}\n"
        progress_text += f"Current Fatigue: {history.current_fatigue}%\n\n"
        
        if history.sessions_by_type:
            progress_text += "Practice Sessions by Type:\n"
            for practice_type, count in history.sessions_by_type.items():
                progress_text += f"  {practice_type.value.replace('_', ' ').title()}: {count} sessions\n"
        else:
            progress_text += "No practice sessions completed yet."
        
        messagebox.showinfo("Development Progress", progress_text)
    
    def _create_practice_controls(self, parent):
        """Create practice session controls"""
        # Selected player info
        self.player_info_frame = ttk.Frame(parent, style='Content.TFrame')
        self.player_info_frame.pack(fill='x', padx=10, pady=10)
        
        self.player_name_label = ttk.Label(self.player_info_frame, text="Select a player to begin practice", 
                                         style='Title.TLabel', font=(self.parent.FONT_FAMILY, 14, 'bold'))
        self.player_name_label.pack()
        
        # Practice type selection
        type_frame = ttk.LabelFrame(parent, text="Practice Type", style='Card.TLabelframe')
        type_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        self.practice_type_var = tk.StringVar()
        self.type_options = [(ptype.value.replace('_', ' ').title(), ptype.value) for ptype in PracticeType]
        self.type_display_to_value = {display: value for display, value in self.type_options}
        
        type_combo_frame = ttk.Frame(type_frame, style='Content.TFrame')
        type_combo_frame.pack(fill='x', padx=10, pady=10)
        
        self.practice_type_combo = ttk.Combobox(type_combo_frame, textvariable=self.practice_type_var,
                                              values=[opt[0] for opt in self.type_options], 
                                              state='readonly', width=25)
        # Configure combobox styling for visibility
        try:
            self.practice_type_combo.configure(foreground='black', fieldbackground='white')
        except:
            try:
                self.practice_type_combo.configure(foreground='black')
            except:
                pass
        self.practice_type_combo.pack(side='left')
        
        # Recommendations button
        ttk.Button(type_combo_frame, text="💡 Get Recommendations", 
                  command=self._show_recommendations, style='TButton').pack(side='right', padx=(10, 0))
        
        # Intensity selection
        intensity_frame = ttk.LabelFrame(parent, text="Intensity Level", style='Card.TLabelframe')
        intensity_frame.pack(fill='x', padx=10, pady=5)
        
        intensity_options_frame = ttk.Frame(intensity_frame, style='Content.TFrame')
        intensity_options_frame.pack(fill='x', padx=10, pady=10)
        
        # Set default intensity to proper enum value
        self.intensity_var = tk.StringVar(value=PracticeIntensity.MODERATE.value)
        intensity_options = [
            ("Light (Low fatigue)", "light"),
            ("Moderate (Balanced)", "moderate"), 
            ("Intense (High gains)", "intense"),
            ("Extreme (Max gains, high fatigue)", "extreme")
        ]
        
        for text, value in intensity_options:
            ttk.Radiobutton(intensity_options_frame, text=text, variable=self.intensity_var,
                           value=value, style='TRadiobutton').pack(anchor='w')
        
        # Duration and trainer quality
        settings_frame = ttk.LabelFrame(parent, text="Session Settings", style='Card.TLabelframe')
        settings_frame.pack(fill='x', padx=10, pady=5)
        
        settings_grid = ttk.Frame(settings_frame, style='Content.TFrame')
        settings_grid.pack(fill='x', padx=10, pady=10)
        
        # Duration
        ttk.Label(settings_grid, text="Duration (minutes):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.duration_var = tk.StringVar(value="60")
        duration_spinbox = ttk.Spinbox(settings_grid, from_=30, to=120, textvariable=self.duration_var, width=10)
        # ttk.Spinbox styling - use background instead of fieldbackground
        try:
            duration_spinbox.configure(foreground='black')
        except:
            pass  # Some styling options may not be available
        duration_spinbox.grid(row=0, column=1, sticky='w')
        
        # Trainer quality
        ttk.Label(settings_grid, text="Trainer Quality:", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        self.trainer_var = tk.StringVar()
        trainer_options = ["Basic (8)", "Good (12)", "Excellent (16)", "Elite (20)"]
        trainer_combo = ttk.Combobox(settings_grid, textvariable=self.trainer_var,
                                   values=trainer_options, state='readonly', width=15)
        trainer_combo.configure(foreground='black')
        try:
            trainer_combo.configure(fieldbackground='white')
        except:
            pass  # fieldbackground may not be available on all systems
        trainer_combo.set("Good (12)")
        trainer_combo.grid(row=1, column=1, sticky='w', pady=(5, 0))
        
        # Practice button
        practice_button_frame = ttk.Frame(parent, style='Content.TFrame')
        practice_button_frame.pack(fill='x', padx=10, pady=20)
        
        self.practice_button = ttk.Button(practice_button_frame, text="🏋️ Start Practice Session", 
                                        command=self._start_practice, style='Accent.TButton',
                                        state='disabled')
        self.practice_button.pack()
        
        # Status label
        self.status_label = ttk.Label(practice_button_frame, text="", style='Content.TLabel')
        self.status_label.pack(pady=(10, 0))
    
    def _create_history_view(self, parent):
        """Create practice history view"""
        # History treeview
        history_columns = {
            'date': ('Date', 100),
            'player': ('Player', 120),
            'type': ('Practice Type', 120),
            'intensity': ('Intensity', 80),
            'duration': ('Duration', 80),
            'gains': ('Skill Gains', 100),
            'fatigue': ('Fatigue Cost', 80)
        }
        
        self.history_tree = ttk.Treeview(parent, columns=list(history_columns.keys()),
                                        show='headings')  # Remove fixed height
        
        for col_id, (header, width) in history_columns.items():
            self.history_tree.heading(col_id, text=header)
            self.history_tree.column(col_id, width=width, anchor='center')
        
        # Scrollbar
        history_scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        history_scrollbar.pack(side='right', fill='y', pady=10)
    
    def _populate_players(self):
        """Populate the player list with filtering and sorting"""
        # Clear existing items
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        
        # Check if we have access to user team data
        user_team = None
        if hasattr(self.parent, 'user_team') and self.parent.user_team:
            user_team = self.parent.user_team
        elif hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
            user_team = self.parent.game_manager.user_team
        else:
            # Show error message in the tree
            error_item = self.player_tree.insert('', 'end', values=(
                "No team data available", "", "", "", "", "", "", ""
            ))
            return
        
        # Get all players
        all_players = (user_team.roster + 
                      user_team.ahl_roster + 
                      user_team.prospects)
        
        # Apply filters
        filter_type = getattr(self, 'filter_var', None)
        if filter_type:
            filter_value = filter_type.get()
            
            if filter_value == "NHL Roster":
                all_players = user_team.roster
            elif filter_value == "AHL Roster":
                all_players = user_team.ahl_roster
            elif filter_value == "Prospects":
                all_players = user_team.prospects
            elif filter_value == "Under 25":
                all_players = [p for p in all_players if p.age < 25]
            elif filter_value == "Needs Development":
                all_players = [p for p in all_players if p.overall_rating() < 14]
        
        # Apply sorting
        sort_type = getattr(self, 'sort_var', None)
        if sort_type:
            sort_value = sort_type.get()
            
            if sort_value == "Name":
                all_players.sort(key=lambda p: p.full_name)
            elif sort_value == "Age":
                all_players.sort(key=lambda p: p.age)
            elif sort_value == "Overall":
                all_players.sort(key=lambda p: p.overall_rating(), reverse=True)
            elif sort_value == "Position":
                all_players.sort(key=lambda p: p.primary_position.value)
            elif sort_value == "Status":
                def status_sort_key(p):
                    if p in user_team.roster:
                        return "1_NHL"
                    elif p in user_team.ahl_roster:
                        return "2_AHL"
                    else:
                        return "3_Prospect"
                all_players.sort(key=status_sort_key)
            elif sort_value == "Last Practice":
                def practice_sort_key(p):
                    history = self.practice_engine.get_player_history(p.id)
                    return history.last_practice_date or date(2000, 1, 1)
                all_players.sort(key=practice_sort_key, reverse=True)
        
        # Populate the tree
        for player in all_players:
            history = self.practice_engine.get_player_history(player.id)
            
            # Determine player status and styling
            if player in user_team.roster:
                status = "NHL"
                tag = 'nhl_player'
            elif player in user_team.ahl_roster:
                status = "AHL"
                tag = 'ahl_player'
            else:
                status = "Prospect"
                tag = 'prospect'
            
            # Special tags for notable players
            if player.age <= 22 and player.overall_rating() >= 14:
                tag = 'young_star'
            elif player.age >= 32:
                tag = 'veteran'
            
            # Calculate potential (simplified)
            potential = "Low"
            if player.age <= 23:
                if player.overall_rating() >= 15:
                    potential = "Elite"
                elif player.overall_rating() >= 13:
                    potential = "High"
                else:
                    potential = "Medium"
            elif player.age <= 27:
                if player.overall_rating() >= 16:
                    potential = "Star"
                else:
                    potential = "Solid"
            else:
                potential = "Limited"
            
            values = (
                player.full_name,
                player.primary_position.value,
                player.age,
                player.overall_rating(),
                potential,
                f"{history.current_fatigue}%",
                history.total_sessions,
                status
            )
            
            item_id = self.player_tree.insert('', 'end', values=values, tags=(player.id, tag))
            
            # Store player reference in tree map for easy access
            if not hasattr(self.parent, 'tree_maps'):
                self.parent.tree_maps = {}
            if 'development_tree_map' not in self.parent.tree_maps:
                self.parent.tree_maps['development_tree_map'] = {}
            self.parent.tree_maps['development_tree_map'][item_id] = player
        
        # Update status bar
        if hasattr(self, 'status_bar'):
            filter_text = getattr(self.filter_var, 'get', lambda: "All")() if hasattr(self, 'filter_var') else "All"
            self.status_bar.config(text=f"Showing {len(all_players)} players • Filter: {filter_text}")
    
    def _on_player_double_click(self, event):
        """Handle double-click for quick practice"""
        if self.selected_player:
            # Show quick practice options
            recommendations = self.practice_engine.get_practice_recommendations(self.selected_player)
            if recommendations:
                # Use the top recommendation for quick practice
                top_recommendation = recommendations[0][0]
                self._quick_practice(top_recommendation)
            else:
                # Default to skating practice
                self._quick_practice(PracticeType.SKATING)
    
    def _on_player_select(self, event):
        """Handle player selection with comprehensive details"""
        selection = self.player_tree.selection()
        if not selection:
            return
        
        # Clear existing details
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        
        item_id = selection[0]
        
        # Get player from tree map
        if (hasattr(self.parent, 'tree_maps') and 
            'development_tree_map' in self.parent.tree_maps and
            item_id in self.parent.tree_maps['development_tree_map']):
            
            self.selected_player = self.parent.tree_maps['development_tree_map'][item_id]
            self._display_comprehensive_player_details()
        else:
            # Fallback: try to find player by name from tree values
            values = self.player_tree.item(item_id, 'values')
            if values and len(values) > 0:
                player_name = values[0]
                
                # Search for player by name
                user_team = None
                if hasattr(self.parent, 'user_team') and self.parent.user_team:
                    user_team = self.parent.user_team
                elif hasattr(self.parent, 'game_manager') and hasattr(self.parent.game_manager, 'user_team'):
                    user_team = self.parent.game_manager.user_team
                
                if user_team:
                    all_players = (user_team.roster + 
                                  user_team.ahl_roster + 
                                  user_team.prospects)
                    
                    for player in all_players:
                        if player.full_name == player_name:
                            self.selected_player = player
                            self._display_comprehensive_player_details()
                            return
            
            # If we get here, show error message
            error_label = ttk.Label(self.details_frame, 
                                   text="Error: Could not load player details. Please try selecting another player.",
                                   style='Content.TLabel', font=(self.parent.FONT_FAMILY, 12))
            error_label.pack(pady=50)
    
    def _display_comprehensive_player_details(self):
        """Display comprehensive player development details"""
        if not self.selected_player:
            return
        
        player = self.selected_player
        history = self.practice_engine.get_player_history(player.id)
        
        # Player Header
        header_frame = ttk.Frame(self.details_frame, style='Content.TFrame')
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Player name and basic info
        name_label = ttk.Label(header_frame, text=player.full_name, 
                              style='Title.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        name_label.pack()
        
        basic_info = f"{player.primary_position.value} • Age {player.age} • Overall: {player.overall_rating()}"
        basic_label = ttk.Label(header_frame, text=basic_info, 
                               style='Content.TLabel', font=(self.parent.FONT_FAMILY, 12))
        basic_label.pack()
        
        # Development Status Section
        status_frame = ttk.LabelFrame(self.details_frame, text="🏒 Development Status", 
                                     style='Card.TLabelframe')
        status_frame.pack(fill='x', pady=(0, 10))
        
        status_content = ttk.Frame(status_frame, style='Content.TFrame')
        status_content.pack(fill='x', padx=10, pady=10)
        
        # Current status
        status_text = f"Fatigue Level: {history.current_fatigue}%\n"
        status_text += f"Total Practice Sessions: {history.total_sessions}\n"
        
        if history.current_schedule:
            schedule = history.current_schedule
            status_text += f"Current Training: {schedule['type'].value.replace('_', ' ').title()}\n"
            status_text += f"Sessions Remaining: {schedule['sessions_remaining']}\n"
        else:
            status_text += "Current Training: None\n"
        
        if history.last_practice_date:
            status_text += f"Last Practice: {history.last_practice_date.strftime('%m/%d/%Y')}"
        else:
            status_text += "Last Practice: Never"
        
        ttk.Label(status_content, text=status_text, style='Content.TLabel').pack(anchor='w')
        
        # Skills Breakdown Section
        skills_frame = ttk.LabelFrame(self.details_frame, text="📊 Current Skills", 
                                     style='Card.TLabelframe')
        skills_frame.pack(fill='x', pady=(0, 10))
        
        skills_content = ttk.Frame(skills_frame, style='Content.TFrame')
        skills_content.pack(fill='x', padx=10, pady=10)
        
        # Create skills grid
        skills_grid = ttk.Frame(skills_content, style='Content.TFrame')
        skills_grid.pack(fill='x')
        
        # Technical Skills
        tech_frame = ttk.Frame(skills_grid, style='Content.TFrame')
        tech_frame.grid(row=0, column=0, sticky='nw', padx=(0, 20))
        
        ttk.Label(tech_frame, text="Technical Skills:", 
                 style='Subtitle.TLabel', font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        
        tech_skills = [
            ("Skating", getattr(player, 'skating', 10)),
            ("Shooting", getattr(player, 'shooting', 10)),
            ("Passing", getattr(player, 'passing', 10)),
            ("Checking", getattr(player, 'checking', 10)),
            ("Defense", getattr(player, 'defense', 10)),
            ("Faceoffs", getattr(player, 'faceoffs', 10))
        ]
        
        for skill_name, skill_value in tech_skills:
            color = 'green' if skill_value >= 15 else 'orange' if skill_value >= 12 else 'red'
            skill_text = f"{skill_name}: {skill_value}"
            ttk.Label(tech_frame, text=skill_text, style='Content.TLabel',
                     foreground=color).pack(anchor='w')
        
        # Mental Skills
        mental_frame = ttk.Frame(skills_grid, style='Content.TFrame')
        mental_frame.grid(row=0, column=1, sticky='nw', padx=(0, 20))
        
        ttk.Label(mental_frame, text="Mental Attributes:", 
                 style='Subtitle.TLabel', font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        
        mental_skills = [
            ("Work Rate", getattr(player, 'work_rate', 10)),
            ("Determination", getattr(player, 'determination', 10)),
            ("Teamwork", getattr(player, 'teamwork', 10)),
            ("Leadership", getattr(player, 'leadership', 10)),
            ("Hockey IQ", getattr(player, 'hockey_iq', 10)),
            ("Vision", getattr(player, 'vision', 10))
        ]
        
        for skill_name, skill_value in mental_skills:
            color = 'green' if skill_value >= 15 else 'orange' if skill_value >= 12 else 'red'
            skill_text = f"{skill_name}: {skill_value}"
            ttk.Label(mental_frame, text=skill_text, style='Content.TLabel',
                     foreground=color).pack(anchor='w')
        
        # Physical Skills
        physical_frame = ttk.Frame(skills_grid, style='Content.TFrame')
        physical_frame.grid(row=0, column=2, sticky='nw')
        
        ttk.Label(physical_frame, text="Physical Attributes:", 
                 style='Subtitle.TLabel', font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        
        physical_skills = [
            ("Strength", getattr(player, 'strength', 10)),
            ("Speed", getattr(player, 'speed', 10)),
            ("Stamina", getattr(player, 'stamina', 10)),
            ("Injury Prone", getattr(player, 'injury_proneness', 10)),
            ("Aggression", getattr(player, 'aggression', 10)),
            ("Bravery", getattr(player, 'bravery', 10))
        ]
        
        for skill_name, skill_value in physical_skills:
            if skill_name == "Injury Prone":
                color = 'red' if skill_value >= 15 else 'orange' if skill_value >= 12 else 'green'
            else:
                color = 'green' if skill_value >= 15 else 'orange' if skill_value >= 12 else 'red'
            skill_text = f"{skill_name}: {skill_value}"
            ttk.Label(physical_frame, text=skill_text, style='Content.TLabel',
                     foreground=color).pack(anchor='w')
        
        # Practice History Section
        if history.sessions_by_type:
            practice_frame = ttk.LabelFrame(self.details_frame, text="🏋️ Practice History", 
                                          style='Card.TLabelframe')
            practice_frame.pack(fill='x', pady=(0, 10))
            
            practice_content = ttk.Frame(practice_frame, style='Content.TFrame')
            practice_content.pack(fill='x', padx=10, pady=10)
            
            practice_text = "Practice Sessions Completed:\n"
            for practice_type, count in history.sessions_by_type.items():
                practice_text += f"• {practice_type.value.replace('_', ' ').title()}: {count} sessions\n"
            
            ttk.Label(practice_content, text=practice_text, style='Content.TLabel').pack(anchor='w')
        
        # Development Recommendations Section
        recommendations_frame = ttk.LabelFrame(self.details_frame, text="💡 Development Recommendations", 
                                             style='Card.TLabelframe')
        recommendations_frame.pack(fill='x', pady=(0, 10))
        
        rec_content = ttk.Frame(recommendations_frame, style='Content.TFrame')
        rec_content.pack(fill='x', padx=10, pady=10)
        
        recommendations = self.practice_engine.get_practice_recommendations(player)
        
        if recommendations:
            rec_text = "Recommended focus areas:\n"
            for i, (practice_type, reason) in enumerate(recommendations[:3], 1):
                practice_name = practice_type.value.replace('_', ' ').title()
                rec_text += f"{i}. {practice_name}: {reason}\n"
        else:
            rec_text = f"{player.full_name} is well-balanced across all areas.\nFocus on maintaining current skill levels."
        
        ttk.Label(rec_content, text=rec_text, style='Content.TLabel').pack(anchor='w')
        
        # Quick Practice Section
        quick_practice_frame = ttk.LabelFrame(self.details_frame, text="⚡ Quick Practice", 
                                            style='Card.TLabelframe')
        quick_practice_frame.pack(fill='x', pady=(0, 10))
        
        qp_content = ttk.Frame(quick_practice_frame, style='Content.TFrame')
        qp_content.pack(fill='x', padx=10, pady=10)
        
        # Quick practice buttons
        qp_buttons = ttk.Frame(qp_content, style='Content.TFrame')
        qp_buttons.pack(fill='x')
        
        if recommendations:
            # Add buttons for top 3 recommendations
            for i, (practice_type, reason) in enumerate(recommendations[:3]):
                practice_name = practice_type.value.replace('_', ' ').title()
                btn = ttk.Button(qp_buttons, text=f"Practice {practice_name}",
                               command=lambda pt=practice_type: self._quick_practice(pt),
                               style='TButton')
                btn.pack(side='left', padx=(0, 5))
        else:
            # Default practice options
            default_practices = [PracticeType.SKATING, PracticeType.SHOOTING, PracticeType.CONDITIONING]
            for practice_type in default_practices:
                practice_name = practice_type.value.replace('_', ' ').title()
                btn = ttk.Button(qp_buttons, text=f"Practice {practice_name}",
                               command=lambda pt=practice_type: self._quick_practice(pt),
                               style='TButton')
                btn.pack(side='left', padx=(0, 5))
        
        # Development Trajectory Section
        trajectory_frame = ttk.LabelFrame(self.details_frame, text="📈 Development Outlook", 
                                        style='Card.TLabelframe')
        trajectory_frame.pack(fill='x', pady=(0, 10))
        
        traj_content = ttk.Frame(trajectory_frame, style='Content.TFrame')
        traj_content.pack(fill='x', padx=10, pady=10)
        
        # Determine development stage and outlook
        if player.age <= 21:
            outlook = "🌱 High Growth Potential - Prime development years"
            outlook_color = 'green'
        elif player.age <= 25:
            outlook = "📈 Good Development Potential - Still growing"
            outlook_color = 'blue'
        elif player.age <= 29:
            outlook = "💪 Peak Performance Years - Focus on maintenance"
            outlook_color = 'orange'
        elif player.age <= 33:
            outlook = "🎯 Veteran Experience - Skill refinement"
            outlook_color = 'purple'
        else:
            outlook = "🏆 Elder Statesman - Leadership development"
            outlook_color = 'red'
        
        ttk.Label(traj_content, text=outlook, style='Content.TLabel',
                 foreground=outlook_color, font=(self.parent.FONT_FAMILY, 11, 'bold')).pack(anchor='w')
        
        # Age-specific development advice
        if player.age <= 21:
            advice = "Focus on fundamental skills like skating, passing, and hockey IQ.\nHigh-intensity training will yield the best results."
        elif player.age <= 25:
            advice = "Develop position-specific skills and game awareness.\nBalanced training approach recommended."
        elif player.age <= 29:
            advice = "Maintain peak physical condition and refine tactical understanding.\nModerate intensity with skill-specific focus."
        else:
            advice = "Focus on leadership, experience sharing, and injury prevention.\nLight to moderate training intensity."
        
        ttk.Label(traj_content, text=advice, style='Content.TLabel').pack(anchor='w', pady=(5, 0))
    
    def _quick_practice(self, practice_type):
        """Execute a quick practice session with optimal settings"""
        if not self.selected_player:
            return
        
        # Determine optimal intensity based on player age and fatigue
        history = self.practice_engine.get_player_history(self.selected_player.id)
        
        if history.current_fatigue > 80:
            messagebox.showwarning("Too Fatigued", 
                                 f"{self.selected_player.full_name} is too fatigued for practice. "
                                 "Let them rest or use light conditioning.")
            return
        
        # Choose intensity based on age and fatigue
        if self.selected_player.age <= 23 and history.current_fatigue < 50:
            intensity = PracticeIntensity.INTENSE
        elif history.current_fatigue < 70:
            intensity = PracticeIntensity.MODERATE
        else:
            intensity = PracticeIntensity.LIGHT
        
        # Quick practice settings
        duration = 60
        trainer_quality = 12  # Good trainer
        
        try:
            session = self.practice_engine.execute_practice(
                self.selected_player, practice_type, intensity, duration, trainer_quality
            )
            
            # Show quick results
            practice_name = practice_type.value.replace('_', ' ').title()
            result_text = f"Quick {practice_name} practice completed!\n"
            result_text += f"Skill gain: +{session.skill_gain:.2f}\n"
            result_text += f"Fatigue: +{session.fatigue_cost}%"
            
            messagebox.showinfo("Practice Complete", result_text)
            
            # Refresh displays
            self._populate_players()
            self._display_comprehensive_player_details()
            
        except Exception as e:
            messagebox.showerror("Practice Error", f"Failed to complete practice: {str(e)}")
    
    def _update_player_info(self):
        """Update selected player information"""
        if not self.selected_player:
            return
        
        player = self.selected_player
        history = self.practice_engine.get_player_history(player.id)
        
        info_text = f"{player.full_name} ({player.primary_position.value}) - Age {player.age}"
        info_text += f"\nFatigue: {history.current_fatigue}% | Sessions: {history.total_sessions}"
        
        self.player_name_label.config(text=info_text)
    
    def _update_practice_availability(self):
        """Update practice button availability"""
        if not self.selected_player:
            self.practice_button.config(state='disabled')
            self.status_label.config(text="Select a player first")
            return
        
        # Check if practice type is selected
        if not self.practice_type_var.get():
            self.practice_button.config(state='disabled')
            self.status_label.config(text="Select practice type")
            return
        
        # Get practice type enum
        practice_type = None
        for ptype in PracticeType:
            if ptype.value.replace('_', ' ').title() == self.practice_type_var.get():
                practice_type = ptype
                break
        
        if not practice_type:
            self.practice_button.config(state='disabled')
            self.status_label.config(text="Invalid practice type")
            return
        
        # Get intensity enum
        intensity = PracticeIntensity(self.intensity_var.get())
        
        # Check if player can practice
        can_practice, reason = self.practice_engine.can_practice(
            self.selected_player, practice_type, intensity
        )
        
        if can_practice:
            self.practice_button.config(state='normal')
            self.status_label.config(text="Ready to practice", foreground='green')
        else:
            self.practice_button.config(state='disabled')
            self.status_label.config(text=reason, foreground='red')
    
    def _show_recommendations(self):
        """Show practice recommendations for selected player"""
        if not self.selected_player:
            messagebox.showwarning("No Player", "Please select a player first")
            return
        
        recommendations = self.practice_engine.get_practice_recommendations(self.selected_player)
        
        if not recommendations:
            messagebox.showinfo("Recommendations", 
                              f"{self.selected_player.full_name} is well-rounded. "
                              "Focus on maintaining current skills.")
            return
        
        rec_text = f"Recommended practice areas for {self.selected_player.full_name}:\n\n"
        for i, (practice_type, reason) in enumerate(recommendations, 1):
            practice_name = practice_type.value.replace('_', ' ').title()
            rec_text += f"{i}. {practice_name}: {reason}\n"
        
        messagebox.showinfo("Practice Recommendations", rec_text)
    
    def _start_practice(self):
        """Start a practice session"""
        if not self.selected_player:
            return
        
        # Get practice parameters
        practice_type_value = self.type_display_to_value.get(self.practice_type_var.get())
        if not practice_type_value:
            messagebox.showerror("Error", "Please select a practice type")
            return
        
        practice_type = PracticeType(practice_type_value)
        
        intensity = PracticeIntensity(self.intensity_var.get())
        duration = int(self.duration_var.get())
        
        # Get trainer quality
        trainer_text = self.trainer_var.get()
        trainer_quality = int(trainer_text.split('(')[1].split(')')[0])
        
        # Execute practice
        try:
            session = self.practice_engine.execute_practice(
                self.selected_player, practice_type, intensity, duration, trainer_quality
            )
            
            # Show results
            self._show_practice_results(session)
            
            # Update displays
            self._populate_players()
            self._update_player_info()
            self._update_practice_availability()
            
        except Exception as e:
            messagebox.showerror("Practice Error", f"Failed to complete practice: {str(e)}")
    
    def _show_practice_results(self, session: PracticeSession):
        """Show practice session results"""
        results_text = f"Practice Session Complete!\n\n"
        results_text += f"Type: {session.practice_type.value.replace('_', ' ').title()}\n"
        results_text += f"Intensity: {session.intensity.value.title()}\n"
        results_text += f"Duration: {session.duration_minutes} minutes\n"
        results_text += f"Skill Improvement: +{session.skill_gain:.2f} points\n"
        results_text += f"Fatigue Cost: +{session.fatigue_cost} points\n\n"
        
        if session.skill_gain > 0.5:
            results_text += "Excellent practice session! 🌟"
        elif session.skill_gain > 0.2:
            results_text += "Good practice session! 👍"
        else:
            results_text += "Light practice session. 💪"
        
        messagebox.showinfo("Practice Results", results_text)
    
    def _update_history(self):
        """Update practice history display"""
        # Overview window doesn't have a history tree - skip this
        if not hasattr(self, 'history_tree'):
            return
        
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        if not hasattr(self.parent, 'user_team') or not self.parent.user_team:
            return
        
        # Get all recent sessions from all players
        all_sessions = []
        all_players = (self.parent.user_team.roster + 
                      self.parent.user_team.ahl_roster + 
                      self.parent.user_team.prospects)
        
        for player in all_players:
            history = self.practice_engine.get_player_history(player.id)
            for session in history.recent_sessions[-10:]:  # Last 10 sessions per player
                all_sessions.append((player, session))
        
        # Sort by date (most recent first)
        all_sessions.sort(key=lambda x: x[1].date_completed, reverse=True)
        
        # Display recent sessions
        for player, session in all_sessions[:20]:  # Show 20 most recent
            values = (
                session.date_completed.strftime("%m/%d/%y"),
                player.full_name,
                session.practice_type.value.replace('_', ' ').title(),
                session.intensity.value.title(),
                f"{session.duration_minutes}m",
                f"+{session.skill_gain:.2f}",
                f"+{session.fatigue_cost}"
            )
            
            self.history_tree.insert('', 'end', values=values)


# Function to test the practice system
def test_practice_system():
    """Test the enhanced practice system"""
    print("🏒 Testing Enhanced Practice System...")
    print("=" * 50)
    
    # Mock player for testing
    class MockPlayer:
        def __init__(self, name, age, position):
            self.id = f"player_{name.lower().replace(' ', '_')}"
            self.full_name = name
            self.age = age
            self.primary_position = position
            
            # Initialize attributes
            self.skating = random.randint(8, 16)
            self.shooting = random.randint(8, 16)
            self.passing = random.randint(8, 16)
            self.checking = random.randint(8, 16)
            self.defense = random.randint(8, 16)
            self.faceoffs = random.randint(8, 16)
            self.work_rate = random.randint(10, 18)
            
        def overall_rating(self):
            return int((self.skating + self.shooting + self.passing + 
                       self.checking + self.defense) / 5)
    
    # Create test players
    from game_classes import PlayerPosition
    players = [
        MockPlayer("Connor McDavid", 24, PlayerPosition.CENTER),
        MockPlayer("Sidney Crosby", 34, PlayerPosition.CENTER),
        MockPlayer("Young Prospect", 19, PlayerPosition.RIGHT_WING)
    ]
    
    # Create practice engine
    engine = PracticeEngine()
    
    print("📋 Testing players:")
    for player in players:
        print(f"  {player.full_name} (Age {player.age}) - Overall: {player.overall_rating()}")
        print(f"    Skating: {player.skating}, Shooting: {player.shooting}, Passing: {player.passing}")
    
    print("\n🏋️ Testing practice sessions...")
    
    # Test different practice types
    test_sessions = [
        (PracticeType.SKATING, PracticeIntensity.MODERATE, 60),
        (PracticeType.SHOOTING, PracticeIntensity.INTENSE, 90),
        (PracticeType.CONDITIONING, PracticeIntensity.LIGHT, 45)
    ]
    
    for player in players[:2]:  # Test with first 2 players
        print(f"\n👤 {player.full_name}:")
        
        for practice_type, intensity, duration in test_sessions:
            can_practice, reason = engine.can_practice(player, practice_type, intensity)
            
            if can_practice:
                old_skating = player.skating
                old_shooting = player.shooting
                
                session = engine.execute_practice(player, practice_type, intensity, duration, 15)
                
                print(f"  ✅ {practice_type.value.title()} ({intensity.value}): "
                      f"+{session.skill_gain:.2f} skill, +{session.fatigue_cost} fatigue")
                
                if practice_type == PracticeType.SKATING and player.skating > old_skating:
                    print(f"     Skating improved: {old_skating} → {player.skating}")
                elif practice_type == PracticeType.SHOOTING and player.shooting > old_shooting:
                    print(f"     Shooting improved: {old_shooting} → {player.shooting}")
            else:
                print(f"  ❌ Cannot practice {practice_type.value}: {reason}")
    
    print("\n💡 Testing recommendations...")
    for player in players:
        recommendations = engine.get_practice_recommendations(player)
        print(f"\n{player.full_name} recommendations:")
        for practice_type, reason in recommendations[:3]:
            print(f"  • {practice_type.value.replace('_', ' ').title()}: {reason}")
    
    print("\n✅ Enhanced Practice System test complete!")


class PracticeCenterWindow(tk.Toplevel):
    """Practice center window for active roster players only"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # Handle practice engine - parent might be the game manager directly or have a game_manager attribute
        if hasattr(parent, 'game_manager'):
            # Parent has a game_manager attribute
            self.practice_engine = getattr(parent.game_manager, 'practice_engine', None)
            if not self.practice_engine:
                self.practice_engine = PracticeEngine()
                parent.game_manager.practice_engine = self.practice_engine
        else:
            # Parent IS the game manager (HockeyManagerGUI)
            self.practice_engine = getattr(parent, 'practice_engine', None)
            if not self.practice_engine:
                self.practice_engine = PracticeEngine()
                parent.practice_engine = self.practice_engine
        
        self.selected_player = None
        
        self.title("Practice Center")
        self.geometry("1000x700")
        self.configure(background=parent.BG_COLOR)
        
        # Make window modal
        self.transient(parent)
        self.grab_set()
        
        self._create_interface()
        self.update_views()
        
        # Center the window
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
    
    def _create_interface(self):
        """Create the practice center interface"""
        # Title
        title_label = ttk.Label(self, text="Practice Center - Active Roster Only", 
                              style='Title.TLabel', font=(self.parent.FONT_FAMILY, 16, 'bold'))
        title_label.pack(pady=(10, 0))
        
        subtitle_label = ttk.Label(self, text="Schedule individual practice sessions for players on the active roster", 
                                 style='Content.TLabel')
        subtitle_label.pack(pady=(0, 10))
        
        # Main content frame with grid
        content_frame = ttk.Frame(self, style='Content.TFrame')
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Configure grid
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Left panel - Player list
        left_panel = self.parent._create_panel(content_frame, "Active Roster Players", 0, 0)
        
        # Player list
        self._create_player_list(left_panel)
        
        # Right panel - Practice controls
        right_panel = self.parent._create_panel(content_frame, "Practice Session", 0, 1)
        
        # Practice controls
        self._create_practice_controls(right_panel)
        
        # Bottom buttons
        button_frame = ttk.Frame(self, style='Content.TFrame')
        button_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Button(button_frame, text="Close", command=self.destroy).pack(side='right')
    
    def _create_player_list(self, parent):
        """Create the active roster player list"""
        # Player tree
        columns = {
            'name': ('Player', 150),
            'position': ('Position', 80),
            'overall': ('Overall', 70),
            'fatigue': ('Fatigue', 70),
            'practice': ('Current Practice', 120)
        }
        
        self.player_tree = self.parent._create_treeview(parent, columns)  # Remove fixed height
        self.player_tree.bind('<<TreeviewSelect>>', self._on_player_select)
        
        # Grid the treeview to match panel layout
        self.player_tree.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # Make tree expandable
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Populate with active roster only
        self._populate_player_tree()
    
    def _populate_player_tree(self):
        """Populate tree with active roster players only"""
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        
        user_team = self.parent.game_manager.user_team
        active_roster = user_team.roster  # Only active roster players
        
        for player in active_roster:
            history = self.practice_engine.get_player_history(player.id)
            
            current_practice = "None"
            if history.current_schedule:
                schedule = history.current_schedule
                practice_type = schedule['type'].value.replace('_', ' ').title()
                intensity = schedule['intensity'].value.replace('_', ' ').title()
                remaining = schedule['sessions_remaining']
                current_practice = f"{practice_type} ({intensity}) - {remaining} left"
            
            item_id = self.player_tree.insert('', 'end', values=(
                player.full_name,
                player.primary_position.value,
                player.overall_rating(),
                f"{history.current_fatigue}%",
                current_practice
            ), tags=(player.id,))
            
            # Store player object reference
            if 'practice_center_tree_map' not in self.parent.tree_maps:
                self.parent.tree_maps['practice_center_tree_map'] = {}
            self.parent.tree_maps['practice_center_tree_map'][item_id] = player
    
    def _on_player_select(self, event):
        """Handle player selection"""
        selection = self.player_tree.selection()
        if selection:
            item_id = selection[0]
            self.selected_player = self.parent.tree_maps.get('practice_center_tree_map', {}).get(item_id)
            self._update_practice_controls()
    
    def _create_practice_controls(self, parent):
        """Create practice controls"""
        self.controls_frame = ttk.Frame(parent, style='Content.TFrame')
        self.controls_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # Make the frame expandable
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        self._update_practice_controls()
    
    def _update_practice_controls(self):
        """Update practice controls based on selected player"""
        # Clear existing controls
        for widget in self.controls_frame.winfo_children():
            widget.destroy()
        
        if not self.selected_player:
            ttk.Label(self.controls_frame, text="Select a player to configure practice",
                     style='Content.TLabel').pack(pady=50)
            return
        
        # Player info
        player_frame = ttk.Frame(self.controls_frame, style='Content.TFrame')
        player_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(player_frame, text=f"Practice for {self.selected_player.full_name}",
                 style='Subtitle.TLabel').pack()
        
        history = self.practice_engine.get_player_history(self.selected_player.id)
        ttk.Label(player_frame, text=f"Current Fatigue: {history.current_fatigue}%",
                 style='Content.TLabel').pack()
        
        # Current schedule info
        if history.current_schedule:
            schedule = history.current_schedule
            schedule_text = (f"Current: {schedule['type'].value.replace('_', ' ').title()} "
                           f"({schedule['intensity'].value.replace('_', ' ').title()}) - "
                           f"{schedule['sessions_remaining']} sessions remaining")
            ttk.Label(player_frame, text=schedule_text, style='Content.TLabel').pack()
            
            # Stop current practice button
            ttk.Button(player_frame, text="Stop Current Practice",
                      command=self._stop_current_practice,
                      style='Danger.TButton').pack(pady=5)
        
        # Practice type selection
        type_frame = ttk.LabelFrame(self.controls_frame, text="Practice Type", style='Card.TLabelframe')
        type_frame.pack(fill='x', pady=5)
        
        self.practice_type_var = tk.StringVar(value=PracticeType.SKATING.value)
        
        type_inner = ttk.Frame(type_frame, style='Content.TFrame')
        type_inner.pack(fill='x', padx=10, pady=10)
        
        for i, practice_type in enumerate(PracticeType):
            row = i // 2
            col = i % 2
            ttk.Radiobutton(type_inner, text=practice_type.value.replace('_', ' ').title(),
                           variable=self.practice_type_var, value=practice_type.value).grid(
                           row=row, column=col, sticky='w', padx=(0, 20), pady=2)
        
        # Intensity selection
        intensity_frame = ttk.LabelFrame(self.controls_frame, text="Intensity", style='Card.TLabelframe')
        intensity_frame.pack(fill='x', pady=5)
        
        self.intensity_var = tk.StringVar(value=PracticeIntensity.MODERATE.value)
        
        intensity_inner = ttk.Frame(intensity_frame, style='Content.TFrame')
        intensity_inner.pack(fill='x', padx=10, pady=10)
        
        for i, intensity in enumerate(PracticeIntensity):
            ttk.Radiobutton(intensity_inner, text=intensity.value.replace('_', ' ').title(),
                           variable=self.intensity_var, value=intensity.value).grid(
                           row=0, column=i, sticky='w', padx=(0, 15), pady=2)
        
        # Schedule settings
        schedule_frame = ttk.LabelFrame(self.controls_frame, text="Schedule", style='Card.TLabelframe')
        schedule_frame.pack(fill='x', pady=5)
        
        schedule_inner = ttk.Frame(schedule_frame, style='Content.TFrame')
        schedule_inner.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(schedule_inner, text="Sessions per week:", style='Content.TLabel').grid(row=0, column=0, sticky='w')
        self.sessions_var = tk.IntVar(value=3)
        sessions_spinbox = ttk.Spinbox(schedule_inner, from_=1, to=7, textvariable=self.sessions_var, width=5)
        try:
            sessions_spinbox.configure(foreground='black')
        except:
            pass
        sessions_spinbox.grid(row=0, column=1, padx=(10, 0))
        
        ttk.Label(schedule_inner, text="Duration (weeks):", style='Content.TLabel').grid(row=1, column=0, sticky='w')
        self.duration_var = tk.IntVar(value=4)
        duration_spinbox = ttk.Spinbox(schedule_inner, from_=1, to=12, textvariable=self.duration_var, width=5)
        try:
            duration_spinbox.configure(foreground='black')
        except:
            pass
        duration_spinbox.grid(row=1, column=1, padx=(10, 0))
        
        # Action buttons
        button_frame = ttk.Frame(self.controls_frame, style='Content.TFrame')
        button_frame.pack(fill='x', pady=10)
        
        ttk.Button(button_frame, text="Start Practice Schedule",
                  command=self._start_practice_schedule,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(button_frame, text="Single Session",
                  command=self._run_single_session).pack(side='left')
    
    def _start_practice_schedule(self):
        """Start a practice schedule for the selected player"""
        if not self.selected_player:
            return
        
        try:
            practice_type = PracticeType(self.practice_type_var.get())
            intensity = PracticeIntensity(self.intensity_var.get())
            sessions_per_week = self.sessions_var.get()
            duration_weeks = self.duration_var.get()
            
            total_sessions = sessions_per_week * duration_weeks
            
            result = self.practice_engine.schedule_practice(
                self.selected_player, practice_type, intensity, total_sessions
            )
            
            if result.success:
                messagebox.showinfo("Practice Scheduled",
                                  f"Practice schedule started for {self.selected_player.full_name}!\n"
                                  f"Type: {practice_type.value.replace('_', ' ').title()}\n"
                                  f"Intensity: {intensity.value.replace('_', ' ').title()}\n"
                                  f"Sessions: {total_sessions}")
                self.update_views()
            else:
                messagebox.showerror("Schedule Failed", result.message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule practice: {str(e)}")
    
    def _run_single_session(self):
        """Run a single practice session"""
        if not self.selected_player:
            messagebox.showwarning("No Player Selected", "Please select a player first.")
            return
        
        try:
            # Convert display value to enum value for practice type
            practice_type_display = self.practice_type_var.get()
            if not practice_type_display:
                messagebox.showwarning("No Practice Type", "Please select a practice type.")
                return
            
            # Check if we have the type_display_to_value mapping (for DevelopmentOverviewWindow)
            if hasattr(self, 'type_display_to_value'):
                practice_type_value = self.type_display_to_value.get(practice_type_display)
                if not practice_type_value:
                    messagebox.showerror("Invalid Practice Type", f"Unknown practice type: {practice_type_display}")
                    return
            else:
                # For PracticeCenterWindow, the value is already the enum value
                practice_type_value = practice_type_display
                
            practice_type = PracticeType(practice_type_value)
            
            # Get intensity value
            intensity_value = self.intensity_var.get()
            if not intensity_value:
                messagebox.showwarning("No Intensity Selected", "Please select an intensity level.")
                return
                
            intensity = PracticeIntensity(intensity_value)
            
            # Check if player can practice
            can_practice, reason = self.practice_engine.can_practice(self.selected_player, practice_type, intensity)
            if not can_practice:
                messagebox.showwarning("Cannot Practice", reason)
                return
            
            # Get trainer quality value
            trainer_quality = 12  # Default to "Good"
            if hasattr(self, 'trainer_var'):
                # DevelopmentOverviewWindow has trainer selection
                trainer_display = self.trainer_var.get()
                if "Basic" in trainer_display:
                    trainer_quality = 8
                elif "Excellent" in trainer_display:
                    trainer_quality = 16
                elif "Elite" in trainer_display:
                    trainer_quality = 20
            # PracticeCenterWindow uses default trainer quality
                
            # Get duration value (different meanings in different windows)
            if hasattr(self, 'type_display_to_value'):
                # DevelopmentOverviewWindow - duration is practice session minutes
                duration = int(self.duration_var.get())
            else:
                # PracticeCenterWindow - use default session duration of 60 minutes
                duration = 60
            
            session = self.practice_engine.execute_practice(
                self.selected_player, practice_type, intensity, duration, trainer_quality
            )
            
            if session:
                messagebox.showinfo("Practice Complete",
                                  f"Practice session completed for {self.selected_player.full_name}!\n"
                                  f"Skill gain: {session.skill_gain:.2f}\n"
                                  f"Fatigue: +{session.fatigue_cost}%\n"
                                  f"Duration: {session.duration_minutes} minutes")
                self.update_views()
            else:
                messagebox.showerror("Practice Failed", "Failed to complete practice session")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run practice: {str(e)}")
            import traceback
            print(f"Practice session error: {e}")
            print(traceback.format_exc())
    
    def _stop_current_practice(self):
        """Stop current practice schedule"""
        if not self.selected_player:
            return
        
        self.practice_engine.stop_practice_schedule(self.selected_player)
        messagebox.showinfo("Practice Stopped", 
                           f"Practice schedule stopped for {self.selected_player.full_name}")
        self.update_views()
    
    def update_views(self):
        """Update all views"""
        self._populate_player_tree()
        self._update_practice_controls()


if __name__ == "__main__":
    test_practice_system()
