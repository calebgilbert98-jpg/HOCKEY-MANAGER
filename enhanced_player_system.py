"""
Enhanced Player System with EHM-Level Depth
Phase 1: Deep Player Psychology & Hidden Attributes
"""

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Dict, List, Optional
from game_classes import PlayerPosition

class PersonalityType(Enum):
    CLUTCH_PERFORMER = "clutch_performer"
    CONSISTENT_GRINDER = "consistent_grinder"
    VOLATILE_STAR = "volatile_star"
    TEAM_PLAYER = "team_player"
    SELFISH_SCORER = "selfish_scorer"
    DEFENSIVE_SPECIALIST = "defensive_specialist"
    ENFORCER = "enforcer"
    PLAYMAKER = "playmaker"
    STEADY_VETERAN = "steady_veteran"
    GRINDER = "grinder"
    INCONSISTENT_PROSPECT = "inconsistent_prospect"

class MoraleLevel(Enum):
    ECSTATIC = 95
    VERY_HAPPY = 85
    HAPPY = 75
    CONTENT = 65
    NEUTRAL = 50
    UNHAPPY = 35
    VERY_UNHAPPY = 25
    MISERABLE = 15

@dataclass
class EnhancedPlayer:
    """EHM-style player with deep attributes and psychology"""
    
    # Basic Info (compatible with existing Player class)
    id: str
    first_name: str
    last_name: str
    age: int
    primary_position: PlayerPosition
    overall: int = 75  # Overall rating
    
    # Core Attributes (using same names as existing Player class for compatibility)
    skating: int = field(default_factory=lambda: random.randint(8, 18))
    shooting: int = field(default_factory=lambda: random.randint(8, 18))
    passing: int = field(default_factory=lambda: random.randint(8, 18))
    checking: int = field(default_factory=lambda: random.randint(8, 18))
    goaltending: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Enhanced Technical Attributes (1-20 scale)
    stickhandling: int = field(default_factory=lambda: random.randint(8, 18))
    shooting_accuracy: int = field(default_factory=lambda: random.randint(8, 18))
    shooting_power: int = field(default_factory=lambda: random.randint(8, 18))
    passing_accuracy: int = field(default_factory=lambda: random.randint(8, 18))
    passing_vision: int = field(default_factory=lambda: random.randint(8, 18))
    skating_speed: int = field(default_factory=lambda: random.randint(8, 18))
    skating_agility: int = field(default_factory=lambda: random.randint(8, 18))
    body_checking: int = field(default_factory=lambda: random.randint(8, 18))
    shot_blocking: int = field(default_factory=lambda: random.randint(8, 18))
    faceoffs: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Goalie-specific attributes
    reflexes: int = field(default_factory=lambda: random.randint(8, 18))
    positioning: int = field(default_factory=lambda: random.randint(8, 18))
    rebound_control: int = field(default_factory=lambda: random.randint(8, 18))
    glove_hand: int = field(default_factory=lambda: random.randint(8, 18))
    blocker_hand: int = field(default_factory=lambda: random.randint(8, 18))
    five_hole: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Physical Attributes
    strength: int = field(default_factory=lambda: random.randint(8, 18))
    stamina: int = field(default_factory=lambda: random.randint(8, 18))
    injury_resistance: int = field(default_factory=lambda: random.randint(8, 18))
    size: int = field(default_factory=lambda: random.randint(8, 18))  # Height/weight factor
    reach: int = field(default_factory=lambda: random.randint(8, 18))
    
    # HIDDEN ATTRIBUTES - The key to EHM-style depth
    # Mental Attributes
    consistency: int = field(default_factory=lambda: random.randint(5, 20))
    pressure_handling: int = field(default_factory=lambda: random.randint(5, 20))
    big_game_performance: int = field(default_factory=lambda: random.randint(5, 20))
    clutch_factor: int = field(default_factory=lambda: random.randint(5, 20))
    focus: int = field(default_factory=lambda: random.randint(5, 20))
    mental_toughness: int = field(default_factory=lambda: random.randint(5, 20))
    
    # Personality Attributes
    leadership: int = field(default_factory=lambda: random.randint(5, 20))
    teamwork: int = field(default_factory=lambda: random.randint(5, 20))
    selfishness: int = field(default_factory=lambda: random.randint(5, 20))
    aggression: int = field(default_factory=lambda: random.randint(5, 20))
    discipline: int = field(default_factory=lambda: random.randint(5, 20))
    work_ethic: int = field(default_factory=lambda: random.randint(5, 20))
    coachability: int = field(default_factory=lambda: random.randint(5, 20))
    
    # Situational Attributes
    home_ice_comfort: int = field(default_factory=lambda: random.randint(5, 20))
    travel_fatigue_resistance: int = field(default_factory=lambda: random.randint(5, 20))
    rivalry_motivation: int = field(default_factory=lambda: random.randint(5, 20))
    playoff_experience: int = field(default_factory=lambda: random.randint(5, 20))
    
    # Tactical IQ Attributes
    offensive_read: int = field(default_factory=lambda: random.randint(5, 20))
    defensive_read: int = field(default_factory=lambda: random.randint(5, 20))
    anticipation: int = field(default_factory=lambda: random.randint(5, 20))
    positioning_iq: int = field(default_factory=lambda: random.randint(5, 20))
    system_adaptability: int = field(default_factory=lambda: random.randint(5, 20))
    
    # Dynamic State Variables
    current_morale: MoraleLevel = field(default=MoraleLevel.NEUTRAL)
    current_form: int = field(default=50)  # 0-100, affects performance
    fatigue_level: int = field(default=0)  # 0-100, higher = more tired
    injury_status: str = field(default="Healthy")
    games_played: int = field(default=0)
    
    # Personality Profile
    personality_type: PersonalityType = field(default=PersonalityType.CONSISTENT_GRINDER)
    
    # Performance Tracking
    season_goals: int = field(default=0)
    season_assists: int = field(default=0)
    season_penalty_minutes: int = field(default=0)
    career_games: int = field(default=0)
    
    # Line Chemistry (player_id -> chemistry_level)
    line_chemistry: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize player based on position and personality"""
        self._assign_personality_type()
        self._adjust_attributes_by_position()
        self._adjust_attributes_by_personality()
    
    @property
    def full_name(self) -> str:
        """Return full name for compatibility with existing code"""
        return f"{self.first_name} {self.last_name}"
    
    def _assign_personality_type(self):
        """Assign personality type based on attributes"""
        # Analyze attributes to determine personality
        if self.clutch_factor >= 16 and self.pressure_handling >= 15:
            self.personality_type = PersonalityType.CLUTCH_PERFORMER
        elif self.consistency >= 16 and self.work_ethic >= 15:
            self.personality_type = PersonalityType.CONSISTENT_GRINDER
        elif self.selfishness >= 16 and self.shooting_accuracy >= 15:
            self.personality_type = PersonalityType.SELFISH_SCORER
        elif self.teamwork >= 16 and self.leadership >= 15:
            self.personality_type = PersonalityType.TEAM_PLAYER
        elif max(self.shooting_accuracy, self.passing_vision) >= 17 and self.consistency <= 12:
            self.personality_type = PersonalityType.VOLATILE_STAR
        elif self.defensive_read >= 16 and self.shot_blocking >= 15:
            self.personality_type = PersonalityType.DEFENSIVE_SPECIALIST
        elif self.aggression >= 17 and self.body_checking >= 16:
            self.personality_type = PersonalityType.ENFORCER
        else:
            self.personality_type = PersonalityType.PLAYMAKER
    
    def _adjust_attributes_by_position(self):
        """Adjust attributes based on position specialization"""
        if self.primary_position == PlayerPosition.GOALIE:
            # Boost goalie-specific attributes
            self.reflexes = min(20, self.reflexes + random.randint(2, 5))
            self.positioning = min(20, self.positioning + random.randint(2, 5))
            self.rebound_control = min(20, self.rebound_control + random.randint(1, 4))
            # Reduce skater attributes
            self.shooting_accuracy = max(5, self.shooting_accuracy - random.randint(3, 6))
            self.body_checking = max(5, self.body_checking - random.randint(2, 5))
        
        elif self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
            # Boost defensive attributes
            self.shot_blocking = min(20, self.shot_blocking + random.randint(2, 4))
            self.defensive_read = min(20, self.defensive_read + random.randint(2, 4))
            self.body_checking = min(20, self.body_checking + random.randint(1, 3))
            # Reduce offensive attributes slightly
            self.shooting_accuracy = max(5, self.shooting_accuracy - random.randint(0, 2))
        
        elif self.primary_position == PlayerPosition.CENTER:
            # Centers need good faceoffs and passing
            self.faceoffs = min(20, self.faceoffs + random.randint(2, 5))
            self.passing_vision = min(20, self.passing_vision + random.randint(1, 3))
            self.offensive_read = min(20, self.offensive_read + random.randint(1, 3))
        
        else:  # Wingers
            # Boost shooting for wingers
            self.shooting_accuracy = min(20, self.shooting_accuracy + random.randint(1, 3))
            self.shooting_power = min(20, self.shooting_power + random.randint(1, 3))
    
    def _adjust_attributes_by_personality(self):
        """Adjust attributes based on personality type"""
        if self.personality_type == PersonalityType.CLUTCH_PERFORMER:
            self.clutch_factor = min(20, self.clutch_factor + 3)
            self.pressure_handling = min(20, self.pressure_handling + 3)
            self.big_game_performance = min(20, self.big_game_performance + 2)
        
        elif self.personality_type == PersonalityType.CONSISTENT_GRINDER:
            self.consistency = min(20, self.consistency + 4)
            self.work_ethic = min(20, self.work_ethic + 3)
            self.discipline = min(20, self.discipline + 2)
        
        elif self.personality_type == PersonalityType.VOLATILE_STAR:
            # High skill but low consistency
            self.shooting_accuracy = min(20, self.shooting_accuracy + 2)
            self.passing_vision = min(20, self.passing_vision + 2)
            self.consistency = max(5, self.consistency - 3)
            self.pressure_handling = max(5, self.pressure_handling - 2)
        
        elif self.personality_type == PersonalityType.SELFISH_SCORER:
            self.shooting_accuracy = min(20, self.shooting_accuracy + 3)
            self.selfishness = min(20, self.selfishness + 4)
            self.teamwork = max(5, self.teamwork - 2)
        
        elif self.personality_type == PersonalityType.TEAM_PLAYER:
            self.teamwork = min(20, self.teamwork + 4)
            self.leadership = min(20, self.leadership + 3)
            self.passing_accuracy = min(20, self.passing_accuracy + 2)
    
    def get_performance_modifier(self, situation: Dict[str, any]) -> float:
        """Get performance modifier based on current situation and player psychology"""
        modifier = 1.0
        
        # Form modifier
        modifier *= (0.7 + (self.current_form / 100) * 0.6)  # 0.7 to 1.3 multiplier
        
        # Morale modifier
        morale_mod = (self.current_morale.value - 50) / 100  # -0.35 to +0.45
        modifier += morale_mod
        
        # Fatigue modifier
        fatigue_penalty = self.fatigue_level / 200  # 0 to 0.5 penalty
        modifier -= fatigue_penalty
        
        # Situational modifiers
        if situation.get('is_home_game'):
            modifier += (self.home_ice_comfort - 10) / 100
        
        if situation.get('is_rivalry_game'):
            modifier += (self.rivalry_motivation - 10) / 100
        
        if situation.get('is_playoff'):
            modifier += (self.playoff_experience - 10) / 100
        
        if situation.get('pressure_level', 0) > 7:  # High pressure situation
            modifier += (self.pressure_handling - 10) / 100
        
        if situation.get('is_clutch_time'):  # Final minutes of close game
            modifier += (self.clutch_factor - 10) / 100
        
        # Consistency check - consistent players perform closer to average
        if self.personality_type == PersonalityType.CONSISTENT_GRINDER:
            # Bring modifier closer to 1.0
            modifier = 1.0 + (modifier - 1.0) * 0.7
        elif self.personality_type == PersonalityType.VOLATILE_STAR:
            # Amplify the modifier (more extreme performance)
            modifier = 1.0 + (modifier - 1.0) * 1.4
        
        return max(0.3, min(2.0, modifier))  # Clamp between 30% and 200%
    
    def make_decision(self, available_actions: List[str], situation: Dict[str, any]) -> str:
        """Make a decision based on personality and situation"""
        action_weights = {}
        
        for action in available_actions:
            base_weight = 1.0
            
            # Personality-based decision making
            if self.personality_type == PersonalityType.SELFISH_SCORER:
                if action == 'shoot':
                    base_weight *= 2.5
                elif action == 'pass':
                    base_weight *= 0.6
            
            elif self.personality_type == PersonalityType.TEAM_PLAYER:
                if action == 'pass':
                    base_weight *= 2.0
                elif action == 'shoot' and situation.get('teammates_open', False):
                    base_weight *= 0.5
            
            elif self.personality_type == PersonalityType.DEFENSIVE_SPECIALIST:
                if action in ['check', 'block_shot', 'clear']:
                    base_weight *= 2.0
                elif action == 'rush':
                    base_weight *= 0.4
            
            elif self.personality_type == PersonalityType.CLUTCH_PERFORMER:
                if situation.get('is_clutch_time') and action == 'shoot':
                    base_weight *= 2.5
            
            # Situational adjustments
            if situation.get('score_differential', 0) < -2:  # Team losing badly
                if action == 'shoot':
                    base_weight *= 1.5  # More aggressive when behind
            
            action_weights[action] = base_weight
        
        # Weighted random selection
        total_weight = sum(action_weights.values())
        rand_value = random.random() * total_weight
        
        cumulative = 0
        for action, weight in action_weights.items():
            cumulative += weight
            if rand_value <= cumulative:
                return action
        
        return available_actions[0]  # Fallback
    
    def update_chemistry(self, teammate_id: str, positive_interaction: bool):
        """Update chemistry with a teammate"""
        current_chemistry = self.line_chemistry.get(teammate_id, 50)
        
        if positive_interaction:
            # Good pass, assist, etc.
            self.line_chemistry[teammate_id] = min(100, current_chemistry + random.randint(1, 3))
        else:
            # Turnover, missed pass, etc.
            self.line_chemistry[teammate_id] = max(0, current_chemistry - random.randint(1, 2))
    
    def update_morale(self, event_type: str, magnitude: int = 1):
        """Update player morale based on events"""
        current_value = self.current_morale.value
        
        morale_changes = {
            'goal_scored': +8,
            'assist': +5,
            'win': +3,
            'loss': -2,
            'penalty': -3,
            'benched': -5,
            'traded': -8,
            'contract_signed': +10,
            'injury': -12
        }
        
        change = morale_changes.get(event_type, 0) * magnitude
        new_value = max(15, min(95, current_value + change))
        
        # Update morale level
        for level in MoraleLevel:
            if new_value >= level.value:
                self.current_morale = level
                break
    
    def overall_rating(self) -> int:
        """Calculate overall rating considering all attributes and current state"""
        if self.primary_position == PlayerPosition.GOALIE:
            base_rating = (
                self.reflexes * 0.25 +
                self.positioning * 0.20 +
                self.rebound_control * 0.15 +
                self.glove_hand * 0.10 +
                self.blocker_hand * 0.10 +
                self.five_hole * 0.10 +
                self.mental_toughness * 0.10
            )
        else:
            # Position-specific weighting
            if self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE, PlayerPosition.DEFENSE]:
                base_rating = (
                    self.defensive_read * 0.20 +
                    self.shot_blocking * 0.15 +
                    self.body_checking * 0.15 +
                    self.passing_accuracy * 0.15 +
                    self.skating_speed * 0.10 +
                    self.positioning_iq * 0.10 +
                    self.strength * 0.10 +
                    self.discipline * 0.05
                )
            else:  # Forwards
                base_rating = (
                    self.shooting_accuracy * 0.20 +
                    self.skating_speed * 0.15 +
                    self.passing_vision * 0.15 +
                    self.offensive_read * 0.15 +
                    self.stickhandling * 0.10 +
                    self.shooting_power * 0.10 +
                    self.anticipation * 0.10 +
                    self.work_ethic * 0.05
                )
        
        # Apply current state modifiers
        performance_mod = self.get_performance_modifier({})
        adjusted_rating = base_rating * performance_mod
        
        return int(max(40, min(99, adjusted_rating)))

# Factory function to create players with realistic attribute distributions
def create_enhanced_player(name: str, position: PlayerPosition, age: int = None) -> EnhancedPlayer:
    """Create a player with realistic attribute distribution"""
    if age is None:
        age = random.randint(18, 35)
    
    jersey = random.randint(1, 99)
    
    player = EnhancedPlayer(
        full_name=name,
        age=age,
        primary_position=position,
        jersey_number=jersey
    )
    
    return player
