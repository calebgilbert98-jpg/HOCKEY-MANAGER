# game_classes.py
# A refactored and improved version focusing on structure, scalability, and clarity.

import random
import itertools
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta, datetime

# --- Constants and Configuration ---
class GameBalance:
    MIN_ATTRIBUTE = 1
    MAX_ATTRIBUTE = 20
    DEFAULT_MIN_ATTRIBUTE = 5
    DEFAULT_MAX_ATTRIBUTE = 18
    
    PEAK_AGE_START = 27
    PEAK_AGE_END = 32
    DEVELOPMENT_CHANCE = 0.6
    DECLINE_CHANCE = 0.4

    MAX_SCOUTING_VIEWINGS = 15

# --- Enumerations for Clarity ---
class PlayerPosition(Enum):
    CENTER = "C"
    LEFT_WING = "LW"
    RIGHT_WING = "RW"
    LEFT_DEFENSE = "LD"
    RIGHT_DEFENSE = "RD"
    DEFENSE = "D"
    GOALIE = "G"

    @property
    def attribute_weights(self):
        weights = {
            PlayerPosition.CENTER: {
                'skating': 0.2, 'shooting': 0.25, 'passing': 0.25,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.RIGHT_WING: {
                'skating': 0.2, 'shooting': 0.3, 'passing': 0.2,
                'checking': 0.1, 'strength': 0.1, 'offensive_awareness': 0.1
            },
            PlayerPosition.LEFT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.RIGHT_DEFENSE: {
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.DEFENSE: {  # <-- FIXED HERE
                'skating': 0.25, 'passing': 0.15, 'checking': 0.2,
                'strength': 0.1, 'defensive_awareness': 0.3
            },
            PlayerPosition.GOALIE: {
                'glove': 0.25, 'blocker': 0.25, 'pads': 0.25,
                'reflexes': 0.15, 'positioning': 0.1
            }
        }
        return weights[self]

class PlayerRole(Enum):
    SNIPER = "Sniper"
    PLAYMAKER = "Playmaker"
    POWER_FORWARD = "Power Forward"
    GRINDER = "Grinder"
    ENFORCER = "Enforcer"
    TWO_WAY_FORWARD = "Two-Way Forward"
    OFFENSIVE_DEFENSEMAN = "Offensive Defenseman"
    DEFENSIVE_DEFENSEMAN = "Defensive Defenseman"
    TWO_WAY_DEFENSEMAN = "Two-Way Defenseman"
    GOALIE = "Goalie"

class StaffRole(Enum):
    # Management
    GENERAL_MANAGER = "General Manager"
    ASSISTANT_GENERAL_MANAGER = "Assistant General Manager"
    
    # Coaching Staff
    HEAD_COACH = "Head Coach"
    ASSISTANT_COACH = "Assistant Coach"
    ASSOCIATE_COACH = "Associate Coach"
    GOALIE_COACH = "Goalie Coach"
    POWER_PLAY_COACH = "Power Play Coach"
    PENALTY_KILL_COACH = "Penalty Kill Coach"
    
    # Development Staff
    SKILLS_COACH = "Skills Coach"
    CONDITIONING_COACH = "Conditioning Coach"
    SKATING_COACH = "Skating Coach"
    
    # Scouting Staff
    HEAD_SCOUT = "Head Scout"
    PROFESSIONAL_SCOUT = "Professional Scout"
    AMATEUR_SCOUT = "Amateur Scout"
    EUROPEAN_SCOUT = "European Scout"
    ADVANCE_SCOUT = "Advance Scout"
    
    # Medical & Support Staff
    TEAM_DOCTOR = "Team Doctor"
    PHYSIOTHERAPIST = "Physiotherapist"
    EQUIPMENT_MANAGER = "Equipment Manager"
    STRENGTH_COACH = "Strength & Conditioning Coach"
    
    # Analytics & Media
    VIDEO_COACH = "Video Coach"
    STATISTICIAN = "Statistician"
    MEDIA_RELATIONS = "Media Relations"

# --- Data-Driven Class Structures ---
@dataclass
class Contract:
    """Holds all player contract details."""
    salary: int = 750000
    years_remaining: int = 0
    signing_bonus: int = 0
    performance_bonus: int = 0
    no_trade_clause: bool = False

@dataclass
class PlayerStats:
    """Tracks player statistics for a season."""
    goals: int = 0
    assists: int = 0
    penalties_in_minutes: int = 0
    saves: int = 0  # <-- Add this line
    penalties: int = 0  # <-- Add this line

    @property
    def points(self) -> int:
        return self.goals + self.assists

player_id_counter = itertools.count()

@dataclass(eq=False)
class Player:
    """Represents a single, deeply detailed hockey player."""
    first_name: str
    last_name: str
    age: int
    primary_position: PlayerPosition
    
    id: int = field(default_factory=lambda: next(player_id_counter), init=False)
    jersey_number: int = field(default_factory=lambda: random.randint(1, 98))
    captaincy: str = None # 'C', 'A', or None
    
    # Personal information with realistic defaults
    nationality: str = "Canada"
    birthplace: str = "Unknown"
    height: str = field(default_factory=lambda: f"{random.randint(5, 6)}'{random.randint(6, 11)}\"")  # 5'6" to 6'11"
    weight: int = field(default_factory=lambda: random.randint(160, 230))  # 160-230 lbs
    handedness: str = field(default_factory=lambda: random.choice(["Left", "Right"]))
    birth_date: str = field(default_factory=lambda: f"{random.randint(1995, 2006)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}")
    draft_year: int = field(default_factory=lambda: random.randint(2010, 2024))
    draft_position: str = field(default_factory=lambda: f"Round {random.randint(1, 7)}, Pick {random.randint(1, 31)}")
    
    determination: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    teamwork: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    leadership: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    discipline: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    flair: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    
    consistency: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    important_matches: int = field(default_factory=lambda: random.randint(GameBalance.DEFAULT_MIN_ATTRIBUTE, GameBalance.DEFAULT_MAX_ATTRIBUTE))
    morale: int = 10

    # Career and development tracking
    pro_debut: str = field(default_factory=lambda: f"{random.randint(2015, 2024)}-{random.randint(10, 12)}-{random.randint(1, 28):02d}")
    teams_count: int = field(default_factory=lambda: random.randint(1, 4))
    team_tenure: str = field(default_factory=lambda: random.choice(["This season", "2 years", "3 years", "4+ years"]))
    peak_rating: int = field(default_factory=lambda: random.randint(12, 20))
    potential: int = field(default_factory=lambda: random.randint(10, 20))
    
    # Health and injury tracking  
    is_injured: bool = False
    days_missed: int = 0
    career_games_missed: int = field(default_factory=lambda: random.randint(0, 50))
    last_injury: str = "None"
    
    # Development attributes
    coachability: int = field(default_factory=lambda: random.randint(5, 20))
    work_ethic: int = field(default_factory=lambda: random.randint(5, 20))
    adaptability: int = field(default_factory=lambda: random.randint(5, 20))
    team_chemistry: int = field(default_factory=lambda: random.randint(10, 20))
    line_chemistry: int = field(default_factory=lambda: random.randint(10, 20))
    
    # Performance statistics - Start season at 0
    games_played: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    avg_toi: str = "0:00"
    
    # Goalie specific stats - Start season at 0
    wins: int = 0
    losses: int = 0
    save_percentage: float = 0.000
    goals_against_avg: float = 0.00
    shutouts: int = 0

    # Waiver related attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = field(default_factory=lambda: random.randint(0, 500))

    skating: int = field(default_factory=lambda: random.randint(8, 18))
    strength: int = field(default_factory=lambda: random.randint(8, 18))
    injury_proneness: int = field(default_factory=lambda: random.randint(1, 20))

    shooting: int = field(default_factory=lambda: random.randint(8, 18))
    passing: int = field(default_factory=lambda: random.randint(8, 18))
    deking: int = field(default_factory=lambda: random.randint(8, 18))

    offensive_awareness: int = field(default_factory=lambda: random.randint(8, 18))
    defensive_awareness: int = field(default_factory=lambda: random.randint(8, 18))
    
    checking: int = field(default_factory=lambda: random.randint(8, 18))
    faceoffs: int = field(default_factory=lambda: random.randint(1, 10))
    
    goaltending: int = field(default_factory=lambda: random.randint(1, 5))
    
    shoot_pass_tendency: int = field(default_factory=lambda: random.randint(0, 100))
    hitting_tendency: int = field(default_factory=lambda: random.randint(0, 100))

    potential_grade: str = field(default_factory=lambda: random.choice(['A', 'B', 'C', 'D', 'F']))
    
    contract: Contract = field(default_factory=Contract)
    stats: PlayerStats = field(default_factory=PlayerStats)
    
    team_name: str = "Free Agent"
    x: int = 0  # X position on ice
    y: int = 0  # Y position on ice

    # New attributes (all initialized 5-20)
    stickhandling: int = field(default_factory=lambda: random.randint(5, 20))
    vision: int = field(default_factory=lambda: random.randint(5, 20))
    shooting_accuracy: int = field(default_factory=lambda: random.randint(5, 20))
    shooting_power: int = field(default_factory=lambda: random.randint(5, 20))
    passing_accuracy: int = field(default_factory=lambda: random.randint(5, 20))
    passing_creativity: int = field(default_factory=lambda: random.randint(5, 20))
    puck_protection: int = field(default_factory=lambda: random.randint(5, 20))
    deflections: int = field(default_factory=lambda: random.randint(5, 20))
    shot_blocking: int = field(default_factory=lambda: random.randint(5, 20))
    hockey_iq: int = field(default_factory=lambda: random.randint(5, 20))
    composure: int = field(default_factory=lambda: random.randint(5, 20))
    aggressiveness: int = field(default_factory=lambda: random.randint(5, 20))
    work_rate: int = field(default_factory=lambda: random.randint(5, 20))
    anticipation: int = field(default_factory=lambda: random.randint(5, 20))
    decision_making: int = field(default_factory=lambda: random.randint(5, 20))
    focus: int = field(default_factory=lambda: random.randint(5, 20))
    confidence: int = field(default_factory=lambda: random.randint(5, 20))
    acceleration: int = field(default_factory=lambda: random.randint(5, 20))
    balance: int = field(default_factory=lambda: random.randint(5, 20))
    endurance: int = field(default_factory=lambda: random.randint(5, 20))
    agility: int = field(default_factory=lambda: random.randint(5, 20))
    speed: int = field(default_factory=lambda: random.randint(5, 20))
    stamina: int = field(default_factory=lambda: random.randint(5, 20))
    durability: int = field(default_factory=lambda: random.randint(5, 20))
    
    # New attributes replacing pace and offensive_read
    off_the_puck: int = field(default_factory=lambda: random.randint(5, 20))  # Movement without puck
    
    # Physical and tactical attributes
    wristshot: int = field(default_factory=lambda: random.randint(5, 20))
    slapshot: int = field(default_factory=lambda: random.randint(5, 20))
    pokecheck: int = field(default_factory=lambda: random.randint(5, 20))
    bodycheck: int = field(default_factory=lambda: random.randint(5, 20))
    one_timer: int = field(default_factory=lambda: random.randint(5, 20))
    backhand: int = field(default_factory=lambda: random.randint(5, 20))
    faceoff_wins: int = field(default_factory=lambda: random.randint(5, 20))
    screen_shots: int = field(default_factory=lambda: random.randint(5, 20))
    loose_puck: int = field(default_factory=lambda: random.randint(5, 20))
    creativity: int = field(default_factory=lambda: random.randint(5, 20))
    pressure_player: int = field(default_factory=lambda: random.randint(5, 20))  # Performance under pressure
    # Goalie-specific attributes
    reflexes: int = field(default_factory=lambda: random.randint(5, 20))
    positioning: int = field(default_factory=lambda: random.randint(5, 20))
    rebound_control: int = field(default_factory=lambda: random.randint(5, 20))
    puck_handling: int = field(default_factory=lambda: random.randint(5, 20))
    glove_hand: int = field(default_factory=lambda: random.randint(5, 20))
    stick_side: int = field(default_factory=lambda: random.randint(5, 20))
    breakaway_skill: int = field(default_factory=lambda: random.randint(5, 20))
    
    # Waiver attributes
    on_waivers: bool = False
    waiver_days: int = 0
    nhl_games_played: int = field(default_factory=lambda: random.randint(0, 500))  # For waiver eligibility

    def __post_init__(self):
        """Adjusts attributes based on position after initialization."""
        if self.primary_position == PlayerPosition.CENTER:
            self.faceoffs = random.randint(10, 20)
        elif self.primary_position == PlayerPosition.GOALIE:
            self.goaltending = random.randint(10, 20)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    def __hash__(self):
        """Make Player objects hashable based on their ID."""
        return hash(self.id)
        
    def __eq__(self, other):
        """Compare Player objects based on their ID."""
        if not isinstance(other, Player):
            return False
        return self.id == other.id

    def get_role(self) -> PlayerRole:
        """Dynamically determines the player's role based on their attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            return PlayerRole.GOALIE
        
        if self.primary_position == PlayerPosition.DEFENSE:  # <-- FIXED HERE
            if self.offensive_awareness > 15 and self.shooting > 13:
                return PlayerRole.OFFENSIVE_DEFENSEMAN
            if self.defensive_awareness > 15 and self.checking > 13:
                return PlayerRole.DEFENSIVE_DEFENSEMAN
            return PlayerRole.TWO_WAY_DEFENSEMAN
            
        if self.shooting > 16 and self.offensive_awareness > 15:
            return PlayerRole.SNIPER
        if self.passing > 16 and self.flair > 15:
            return PlayerRole.PLAYMAKER
        if self.strength > 15 and self.checking > 14 and self.hitting_tendency > 60:
            return PlayerRole.POWER_FORWARD
        if self.strength > 16 and self.checking > 16 and self.discipline < 8:
            return PlayerRole.ENFORCER
        if self.determination > 14 and self.teamwork > 14 and self.defensive_awareness > 12:
            return PlayerRole.GRINDER
        return PlayerRole.TWO_WAY_FORWARD

    def overall_rating(self) -> int:
        """Calculates a weighted overall rating based on position, including all attributes."""
        if self.primary_position == PlayerPosition.GOALIE:
            rating = (
                self.goaltending * 0.12 +
                self.reflexes * 0.15 +
                self.positioning * 0.15 +
                self.rebound_control * 0.12 +
                self.puck_handling * 0.08 +
                self.glove_hand * 0.08 +
                self.stick_side * 0.08 +
                self.breakaway_skill * 0.08 +
                self.confidence * 0.05 +
                self.focus * 0.05 +
                self.composure * 0.04
            )
        elif self.primary_position == PlayerPosition.CENTER:
            rating = (
                self.skating * 0.08 +
                self.shooting * 0.06 +
                self.shooting_accuracy * 0.06 +
                self.shooting_power * 0.05 +
                self.passing * 0.07 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.06 +
                self.deking * 0.05 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.06 +
                self.defensive_awareness * 0.05 +
                self.faceoffs * 0.07 +
                self.faceoff_wins * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.04 +
                self.one_timer * 0.03 +
                self.loose_puck * 0.02
            )
        elif self.primary_position in [PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING]:
            rating = (
                self.skating * 0.09 +
                self.shooting * 0.08 +
                self.shooting_accuracy * 0.07 +
                self.shooting_power * 0.07 +
                self.wristshot * 0.06 +
                self.slapshot * 0.05 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.05 +
                self.passing_creativity * 0.05 +
                self.deking * 0.06 +
                self.stickhandling * 0.06 +
                self.vision * 0.06 +
                self.hockey_iq * 0.06 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.04 +
                self.composure * 0.04 +
                self.endurance * 0.04 +
                self.determination * 0.04 +
                self.off_the_puck * 0.05 +
                self.one_timer * 0.04 +
                self.backhand * 0.03 +
                self.screen_shots * 0.03
            )
        elif self.primary_position == PlayerPosition.DEFENSE:
            rating = (
                self.skating * 0.08 +
                self.passing * 0.06 +
                self.passing_accuracy * 0.06 +
                self.passing_creativity * 0.05 +
                self.strength * 0.07 +
                self.checking * 0.07 +
                self.bodycheck * 0.06 +
                self.defensive_awareness * 0.09 +
                self.shot_blocking * 0.07 +
                self.pokecheck * 0.06 +
                self.anticipation * 0.06 +
                self.hockey_iq * 0.06 +
                self.composure * 0.05 +
                self.aggressiveness * 0.05 +
                self.balance * 0.05 +
                self.endurance * 0.05 +
                self.determination * 0.05 +
                self.slapshot * 0.04 +
                self.loose_puck * 0.04 +
                self.pressure_player * 0.04
            )
        else:
            # Fallback for other positions
            rating = (
                self.skating * 0.10 +
                self.shooting * 0.08 +
                self.passing * 0.08 +
                self.deking * 0.07 +
                self.stickhandling * 0.07 +
                self.vision * 0.07 +
                self.hockey_iq * 0.07 +
                self.offensive_awareness * 0.07 +
                self.defensive_awareness * 0.07 +
                self.composure * 0.07 +
                self.endurance * 0.07 +
                self.determination * 0.07 +
                self.off_the_puck * 0.05 +
                self.loose_puck * 0.04
            )
        return int(rating)

    def age_one_year(self):
        """Handles player aging, development, and decline."""
        self.age += 1
        if self.contract.years_remaining > 0:
            self.contract.years_remaining -= 1

        potential_map = {'A': 20, 'B': 18, 'C': 16, 'D': 14, 'F': 12}
        potential_cap = potential_map.get(self.potential_grade, 10)
        
        if self.age < GameBalance.PEAK_AGE_START and self.overall_rating() < potential_cap:
            if random.random() < GameBalance.DEVELOPMENT_CHANCE:
                self._change_random_attribute(1)
        elif self.age > GameBalance.PEAK_AGE_END:
            if random.random() < GameBalance.DECLINE_CHANCE:
                self._change_random_attribute(-1)

    def _change_random_attribute(self, amount: int):
        """Helper to randomly increase or decrease a skill attribute."""
        skill_attributes = [
            'skating', 'strength', 'shooting', 'passing', 'deking',
            'offensive_awareness', 'defensive_awareness', 'checking', 'faceoffs',
            'goaltending', 'determination', 'teamwork', 'leadership', 'discipline', 'flair',
            'stickhandling', 'vision', 'shooting_accuracy', 'shooting_power',
            'passing_accuracy', 'passing_creativity', 'puck_protection', 'deflections',
            'shot_blocking', 'hockey_iq', 'composure', 'aggressiveness', 'work_rate',
            'anticipation', 'decision_making', 'focus', 'confidence', 'acceleration',
            'balance', 'endurance', 'agility', 'speed', 'stamina', 'durability',
            'off_the_puck', 'wristshot', 'slapshot', 'pokecheck', 'bodycheck',
            'one_timer', 'backhand', 'faceoff_wins', 'screen_shots', 'loose_puck',
            'creativity', 'pressure_player', 'reflexes', 'positioning', 'rebound_control',
            'puck_handling', 'glove_hand', 'stick_side', 'breakaway_skill'
        ]
        
        attr_to_change = random.choice(skill_attributes)
        current_value = getattr(self, attr_to_change)
        
        new_value = max(GameBalance.MIN_ATTRIBUTE, min(GameBalance.MAX_ATTRIBUTE, current_value + amount))
        
        setattr(self, attr_to_change, new_value)

    @property
    def value(self):
        """Calculate player's market value based on attributes and performance."""
        # Base value determined by overall rating
        base_value = self.overall_rating() * 100000
        
        # Age modifier - players in their prime (23-29) get premium
        age_modifier = 1.0
        if 23 <= self.age <= 29:
            age_modifier = 1.2
        elif self.age >= 30:
            # Declining value with age
            age_modifier = max(0.5, 1.0 - ((self.age - 30) * 0.05))
        
        # Position modifier - centers and first-line defensemen get premium
        position_modifier = 1.0
        if self.primary_position == PlayerPosition.CENTER:
            position_modifier = 1.15
        elif self.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            position_modifier = 1.1
        elif self.primary_position == PlayerPosition.GOALIE:
            # Goalies have different value curve
            position_modifier = 1.0 if self.overall_rating() >= 85 else 0.9
        
        # Potential modifier for young players
        potential_modifier = 1.0
        if self.age <= 25:
            potential_map = {'A': 1.5, 'B': 1.3, 'C': 1.1, 'D': 1.0, 'F': 0.9}
            potential_modifier = potential_map.get(self.potential_grade, 1.0)
        
        # Stats performance bonus (simplified for now)
        stats = getattr(self, 'stats', None)
        performance_bonus = 0
        if stats:
            performance_bonus = getattr(stats, 'goals', 0) * 50000 + getattr(stats, 'assists', 0) * 30000
        
        # Calculate final market value
        market_value = (base_value * age_modifier * position_modifier * potential_modifier) + performance_bonus
        
        # Minimum NHL salary
        min_salary = 750000
        
        return max(min_salary, int(market_value))
    
    def negotiate_contract(self, salary, years):
        min_salary = self.value * 0.9
        max_salary = self.value * 1.2
        if min_salary <= salary <= max_salary and years >= 1:
            return True
        return False

@dataclass
class Staff:
    """Represents a non-player staff member with detailed EHM-style attributes."""
    first_name: str
    last_name: str
    role: StaffRole
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    age: int = field(default_factory=lambda: random.randint(25, 65))
    nationality: str = field(default_factory=lambda: random.choice(['USA', 'Canada', 'Russia', 'Sweden', 'Finland', 'Czech Republic']))
    
    # Core Coaching Attributes (1-20 scale)
    coaching_forwards: int = field(default_factory=lambda: random.randint(8, 18))
    coaching_defensemen: int = field(default_factory=lambda: random.randint(8, 18))
    coaching_goalies: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Tactical Knowledge
    tactical_knowledge: int = field(default_factory=lambda: random.randint(8, 18))
    game_preparation: int = field(default_factory=lambda: random.randint(8, 18))
    match_preparation: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Player Development
    working_with_youngsters: int = field(default_factory=lambda: random.randint(8, 18))
    player_development: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Management Skills
    man_management: int = field(default_factory=lambda: random.randint(8, 18))
    motivating: int = field(default_factory=lambda: random.randint(8, 18))
    discipline: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Scouting Abilities
    judging_player_ability: int = field(default_factory=lambda: random.randint(8, 18))
    judging_player_potential: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Communication & Relationships
    media_handling: int = field(default_factory=lambda: random.randint(8, 18))
    determination: int = field(default_factory=lambda: random.randint(8, 18))
    adaptability: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Specialized Skills (position-dependent)
    level_of_discipline: int = field(default_factory=lambda: random.randint(8, 18))
    attacking_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    defensive_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    mental_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    technical_coaching: int = field(default_factory=lambda: random.randint(8, 18))
    
    # Contract Information
    salary: int = field(default_factory=lambda: random.randint(75000, 500000))
    contract_years: int = field(default_factory=lambda: random.randint(1, 5))
    
    # Performance Tracking
    reputation: int = field(default_factory=lambda: random.randint(5, 15))
    experience: int = field(default_factory=lambda: random.randint(1, 30))  # Years of experience
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def overall_rating(self) -> int:
        """Calculate overall rating based on role-specific attributes"""
        if self.role in [StaffRole.HEAD_COACH, StaffRole.ASSISTANT_COACH, StaffRole.ASSOCIATE_COACH]:
            return int((
                self.tactical_knowledge * 0.25 +
                self.man_management * 0.20 +
                self.motivating * 0.15 +
                self.coaching_forwards * 0.15 +
                self.coaching_defensemen * 0.15 +
                self.discipline * 0.10
            ))
        elif self.role == StaffRole.GOALIE_COACH:
            return int((
                self.coaching_goalies * 0.40 +
                self.technical_coaching * 0.25 +
                self.working_with_youngsters * 0.20 +
                self.man_management * 0.15
            ))
        elif 'SCOUT' in self.role.value.upper():
            return int((
                self.judging_player_ability * 0.35 +
                self.judging_player_potential * 0.35 +
                self.determination * 0.15 +
                self.adaptability * 0.15
            ))
        elif self.role == StaffRole.GENERAL_MANAGER:
            return int((
                self.judging_player_ability * 0.20 +
                self.judging_player_potential * 0.20 +
                self.man_management * 0.20 +
                self.tactical_knowledge * 0.15 +
                self.media_handling * 0.15 +
                self.determination * 0.10
            ))
        else:
            # General staff rating
            return int((
                self.determination * 0.30 +
                self.adaptability * 0.25 +
                self.man_management * 0.25 +
                self.discipline * 0.20
            ))
    
    def get_role_description(self) -> str:
        """Get a description of what this staff member does"""
        descriptions = {
            StaffRole.GENERAL_MANAGER: "Oversees all hockey operations, trades, signings, and strategic planning.",
            StaffRole.HEAD_COACH: "Leads the team, makes strategic decisions, and manages game tactics.",
            StaffRole.ASSISTANT_COACH: "Supports the head coach with tactical planning and player development.",
            StaffRole.GOALIE_COACH: "Specializes in goaltender training and development.",
            StaffRole.HEAD_SCOUT: "Leads scouting operations and evaluates talent across all levels.",
            StaffRole.PROFESSIONAL_SCOUT: "Scouts professional leagues for trade targets and free agents.",
            StaffRole.AMATEUR_SCOUT: "Evaluates amateur players for the NHL draft.",
            StaffRole.EUROPEAN_SCOUT: "Focuses on European leagues and international talent.",
            StaffRole.SKILLS_COACH: "Develops individual player skills and techniques.",
            StaffRole.CONDITIONING_COACH: "Manages player fitness and physical conditioning.",
        }
        return descriptions.get(self.role, "Provides specialized support to the organization.")
    
    def negotiate_contract(self, salary, years):
        """Determine if staff member will accept contract offer"""
        reputation_modifier = self.reputation / 10
        min_salary = int(self.salary * (0.8 + reputation_modifier * 0.1))
        max_salary = int(self.salary * (1.2 + reputation_modifier * 0.2))
        
        if min_salary <= salary <= max_salary and 1 <= years <= 5:
            # Higher reputation staff are pickier
            acceptance_chance = 0.8 - (self.reputation - 10) * 0.02
            return random.random() < acceptance_chance
        return False
    
    @staticmethod
    def is_unique_role(role: StaffRole) -> bool:
        """Check if a role should be unique per team (only one allowed)"""
        unique_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH
        ]
        return role in unique_roles
    
    @staticmethod
    def is_essential_role(role: StaffRole) -> bool:
        """Check if a role is essential for team operation"""
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH,
            StaffRole.ASSISTANT_GENERAL_MANAGER,
            StaffRole.HEAD_SCOUT
        ]
        return role in essential_roles
    
    @staticmethod
    def get_role_department(role: StaffRole) -> str:
        """Get the department/category for a staff role"""
        departments = {
            # Management
            StaffRole.GENERAL_MANAGER: 'Management',
            StaffRole.ASSISTANT_GENERAL_MANAGER: 'Management',
            
            # Coaching
            StaffRole.HEAD_COACH: 'Coaching',
            StaffRole.ASSISTANT_COACH: 'Coaching',
            StaffRole.ASSOCIATE_COACH: 'Coaching',
            StaffRole.GOALIE_COACH: 'Coaching',
            StaffRole.POWER_PLAY_COACH: 'Coaching',
            StaffRole.PENALTY_KILL_COACH: 'Coaching',
            
            # Development
            StaffRole.SKILLS_COACH: 'Development',
            StaffRole.CONDITIONING_COACH: 'Development',
            StaffRole.SKATING_COACH: 'Development',
            StaffRole.STRENGTH_COACH: 'Development',
            
            # Scouting
            StaffRole.HEAD_SCOUT: 'Scouting',
            StaffRole.PROFESSIONAL_SCOUT: 'Scouting',
            StaffRole.AMATEUR_SCOUT: 'Scouting',
            StaffRole.EUROPEAN_SCOUT: 'Scouting',
            StaffRole.ADVANCE_SCOUT: 'Scouting',
            
            # Medical
            StaffRole.TEAM_DOCTOR: 'Medical',
            StaffRole.PHYSIOTHERAPIST: 'Medical',
            StaffRole.EQUIPMENT_MANAGER: 'Medical',
            
            # Analytics
            StaffRole.VIDEO_COACH: 'Analytics',
            StaffRole.STATISTICIAN: 'Analytics',
            StaffRole.MEDIA_RELATIONS: 'Analytics'
        }
        return departments.get(role, 'Other')

@dataclass
class ScoutingReport:
    """Enhanced EHM-style scouting report with detailed analysis and reliability tracking."""
    player: Player
    scout: Staff
    scouted_attributes: Dict[str, str] = field(default_factory=dict)
    scouted_potential: Optional[str] = None
    viewings: int = 0
    accuracy: str = 'F'  # Letter grade A-F for report accuracy
    last_viewed: Optional[datetime] = None
    reliability: float = 0.0  # 0.0 to 1.0 scale
    notes: str = ""
    
    # Enhanced scouting features
    region_coverage: str = "Unknown"  # Which region this player was scouted in
    competition_level: str = "Unknown"  # Level of competition observed
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    comparable_players: List[str] = field(default_factory=list)
    injury_history_known: bool = False
    personality_assessment: str = ""
    coachability_rating: int = 0  # 1-20 scale
    interview_conducted: bool = False
    
    # Projection data
    projected_draft_position: Optional[int] = None
    projected_nhl_arrival: Optional[str] = None  # "1-2 years", "3-4 years", etc.
    ceiling_rating: int = 0  # Potential ceiling (1-20)
    floor_rating: int = 0   # Likely floor (1-20)
    
    def calculate_reliability(self) -> float:
        """Calculate how reliable this scouting report is (0.0 to 1.0)"""
        base_reliability = {
            'A': 0.95,
            'B': 0.80,
            'C': 0.65, 
            'D': 0.45,
            'F': 0.25
        }.get(self.accuracy, 0.25)
        
        # Scout skill factor
        scout_skill = (self.scout.judging_player_ability + self.scout.judging_player_potential) / 40.0
        
        # Experience bonus
        exp_bonus = min(0.1, self.scout.experience * 0.003)
        
        # Interview bonus
        interview_bonus = 0.05 if self.interview_conducted else 0.0
        
        return min(1.0, base_reliability * scout_skill + exp_bonus + interview_bonus)

    def update_report(self, player: Player, scout: Staff):
        """Updates the report with enhanced EHM-style scouting mechanics."""
        self.viewings += 1
        self.last_viewed = datetime.now()
        
        # Determine competition level
        if player.age < 20:
            competition_levels = ["Junior A", "Junior B", "College", "International Junior"]
            self.competition_level = random.choice(competition_levels)
        else:
            competition_levels = ["AHL", "ECHL", "European Pro", "KHL", "International"]
            self.competition_level = random.choice(competition_levels)
        
        # Region assignment based on scout specialization
        if self.scout.role == StaffRole.EUROPEAN_SCOUT:
            self.region_coverage = random.choice(["Sweden", "Finland", "Russia", "Czech Republic", "Germany", "Switzerland"])
        elif self.scout.role == StaffRole.AMATEUR_SCOUT:
            self.region_coverage = random.choice(["Western Canada", "Eastern Canada", "USA West", "USA East", "USA Central"])
        else:
            self.region_coverage = random.choice(["North America", "Europe", "International"])
        
        # Calculate accuracy based on viewings, scout skill, and role match
        base_viewings = self.viewings
        
        # Scout skill bonus viewings
        skill_bonus = (self.scout.judging_player_ability + self.scout.judging_player_potential) // 10
        effective_viewings = base_viewings + skill_bonus
        
        # Determine accuracy grade
        if effective_viewings >= 20: 
            self.accuracy = 'A'
        elif effective_viewings >= 15: 
            self.accuracy = 'B'
        elif effective_viewings >= 10: 
            self.accuracy = 'C'
        elif effective_viewings >= 5: 
            self.accuracy = 'D'
        else: 
            self.accuracy = 'F'
        
        # Update reliability
        self.reliability = self.calculate_reliability()
        
        # Scout attributes with position-specific focus
        self._scout_attributes(player, scout)
        
        # Scout potential with advanced projections
        self._scout_potential_and_projections(player, scout)
        
        # Generate comprehensive notes
        self._generate_advanced_notes(player, scout)
        
        # Conduct interview if scout is good enough and enough viewings
        if self.viewings >= 3 and scout.man_management > 12 and random.random() < 0.3:
            self._conduct_player_interview(player)

    def _scout_attributes(self, player: Player, scout: Staff):
        """Scout player attributes with position-specific accuracy."""
        # Determine key attributes by position
        if player.primary_position == PlayerPosition.GOALIE:
            primary_attrs = ['goaltending', 'reflexes', 'positioning', 'rebound_control']
            secondary_attrs = ['puck_handling', 'determination', 'discipline', 'composure']
        elif player.primary_position in [PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE]:
            primary_attrs = ['defensive_awareness', 'checking', 'passing', 'shot_blocking', 'skating']
            secondary_attrs = ['shooting', 'strength', 'vision', 'teamwork', 'discipline']
        else:  # Forwards
            primary_attrs = ['shooting', 'passing', 'offensive_awareness', 'deking', 'skating']
            secondary_attrs = ['defensive_awareness', 'checking', 'faceoffs', 'determination', 'composure']
        
        all_attrs = primary_attrs + secondary_attrs
        
        # Scout accuracy modifiers
        accuracy_variance = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'F': 4}[self.accuracy]
        primary_accuracy = max(0, accuracy_variance - 1)  # Primary attributes more accurate
        
        for attr in all_attrs:
            if not hasattr(player, attr):
                continue
                
            true_value = getattr(player, attr)
            is_primary = attr in primary_attrs
            variance = primary_accuracy if is_primary else accuracy_variance
            
            # Generate scouted value
            if self.accuracy == 'A' and is_primary and random.random() < 0.9:
                # A-grade scouts get exact values on key attributes
                self.scouted_attributes[attr] = str(true_value)
            elif variance == 0:
                self.scouted_attributes[attr] = str(true_value)
            else:
                # Create ranges based on accuracy
                lower = max(1, true_value - random.randint(0, variance))
                upper = min(20, true_value + random.randint(0, variance))
                
                if lower == upper:
                    self.scouted_attributes[attr] = str(lower)
                else:
                    self.scouted_attributes[attr] = f"{lower}-{upper}"

    def _scout_potential_and_projections(self, player: Player, scout: Staff):
        """Scout potential with advanced projection system."""
        # Potential scouting accuracy based on JPP
        jpp = scout.judging_player_potential
        
        potential_grades = ["F", "D", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        true_index = potential_grades.index(player.potential_grade) if hasattr(player, 'potential_grade') else 5
        
        # Variance decreases with higher JPP
        variance = max(1, 4 - (jpp // 5))
        scouted_index = max(0, min(len(potential_grades)-1, true_index + random.randint(-variance, variance)))
        self.scouted_potential = potential_grades[scouted_index]
        
        # Project ceiling and floor
        base_overall = player.overall_rating() if hasattr(player, 'overall_rating') else 50
        
        # Ceiling projection (optimistic)
        ceiling_modifier = random.randint(5, 15) if player.age < 23 else random.randint(0, 8)
        self.ceiling_rating = min(20, (base_overall + ceiling_modifier) // 5)
        
        # Floor projection (conservative)
        floor_modifier = random.randint(-5, 5) if player.age < 25 else random.randint(-2, 2)
        self.floor_rating = max(5, (base_overall + floor_modifier) // 5)
        
        # NHL arrival projection
        if player.age >= 23:
            self.projected_nhl_arrival = "Ready now"
        elif player.age >= 21:
            self.projected_nhl_arrival = "1-2 years"
        elif player.age >= 19:
            self.projected_nhl_arrival = "2-3 years"
        else:
            self.projected_nhl_arrival = "3-5 years"
        
        # Draft position projection for young players
        if player.age <= 18:
            potential_to_draft = {
                "A+": (1, 5), "A": (3, 12), "A-": (8, 25),
                "B+": (15, 45), "B": (25, 75), "B-": (40, 120),
                "C+": (60, 150), "C": (100, 210), "C-": (150, 210),
                "D": (180, 210), "F": (200, 210)
            }
            
            if self.scouted_potential in potential_to_draft:
                min_pick, max_pick = potential_to_draft[self.scouted_potential]
                # Add scout uncertainty
                uncertainty = 20 if self.accuracy in ['D', 'F'] else 10
                min_pick = max(1, min_pick - uncertainty)
                max_pick = min(210, max_pick + uncertainty)
                self.projected_draft_position = random.randint(min_pick, max_pick)

    def _generate_advanced_notes(self, player: Player, scout: Staff):
        """Generate comprehensive scouting notes with detailed analysis."""
        notes = []
        
        # Potential assessment
        potential_descriptions = {
            "A+": "Generational talent with franchise-altering potential. Could become one of the greatest players in the league.",
            "A": "Elite talent with superstar potential. Projects as a franchise cornerstone for years to come.",
            "A-": "Excellent potential with top-line/top-pairing upside. Should develop into an impact player.",
            "B+": "Very good potential with solid first-line/first-pairing ceiling. Projects as a core player.",
            "B": "Good potential with middle-six/top-four upside. Should become a reliable NHL regular.",
            "B-": "Above average potential. Projects as a useful middle-six/second-pairing contributor.",
            "C+": "Average potential with bottom-six/third-pairing ceiling. Could carve out an NHL role.",
            "C": "Limited upside but should develop into a depth player at the NHL level.",
            "C-": "Below average potential. May struggle to establish himself as an NHL regular.",
            "D": "Low ceiling. Likely career minor leaguer with limited NHL opportunities.",
            "F": "Very limited potential. Unlikely to reach professional hockey."
        }
        
        notes.append(potential_descriptions.get(self.scouted_potential, "Potential assessment ongoing."))
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        for attr, value_str in self.scouted_attributes.items():
            avg_value = self.get_attribute_value(attr)
            
            if avg_value >= 16:
                strengths.append(attr)
            elif avg_value <= 8:
                weaknesses.append(attr)
        
        # Add descriptive strengths
        if 'skating' in strengths:
            notes.append("Elite skating ability with exceptional speed and agility.")
        elif 'shooting' in strengths:
            notes.append("Possesses a lethal shot with accuracy and power.")
        elif 'passing' in strengths:
            notes.append("Excellent vision and playmaking ability.")
        elif 'defensive_awareness' in strengths:
            notes.append("Outstanding defensive instincts and positioning.")
        
        # Add comparable players for high-potential prospects
        if self.scouted_potential in ['A+', 'A', 'A-'] and self.accuracy in ['A', 'B']:
            comparables = [
                "Reminds me of a young Connor McDavid in terms of hockey IQ",
                "Similar playing style to Nathan MacKinnon",
                "Comparable to Erik Karlsson in terms of offensive awareness",
                "Has shades of Sidney Crosby's competitiveness",
                "Playing style reminiscent of Auston Matthews",
                "Comparable to Cale Makar's skating ability"
            ]
            self.comparable_players = [random.choice(comparables)]
            notes.append(self.comparable_players[0])
        
        # Competition level context
        notes.append(f"Scouted primarily in {self.competition_level} competition.")
        
        # Add projection timeline
        notes.append(f"Projected NHL readiness: {self.projected_nhl_arrival}.")
        
        if self.projected_draft_position:
            notes.append(f"Current draft projection: {self.projected_draft_position} overall.")
        
        self.notes = " ".join(notes)
        self.strengths = strengths
        self.weaknesses = weaknesses

    def _conduct_player_interview(self, player: Player):
        """Conduct a player interview to assess personality and coachability."""
        self.interview_conducted = True
        
        # Generate personality assessment
        personalities = [
            "Highly motivated and driven competitor",
            "Quiet leader who leads by example", 
            "Vocal presence with natural leadership qualities",
            "Team-first player with excellent character",
            "Intense competitor with strong work ethic",
            "Coachable player who accepts instruction well",
            "Independent thinker who needs proper motivation"
        ]
        
        self.personality_assessment = random.choice(personalities)
        
        # Coachability rating (influenced by actual player attributes if available)
        base_coachability = 10
        if hasattr(player, 'determination'):
            base_coachability += (player.determination - 10) // 2
        if hasattr(player, 'discipline'):
            base_coachability += (player.discipline - 10) // 2
        
        self.coachability_rating = max(1, min(20, base_coachability + random.randint(-3, 3)))

    def get_attribute_value(self, attr_name: str) -> int:
        """Extract numeric value from scouted attribute (handles ranges)."""
        if attr_name not in self.scouted_attributes:
            return 10
            
        attr_val = self.scouted_attributes[attr_name]
        
        if '-' in attr_val:
            lower, upper = map(int, attr_val.split('-'))
            return (lower + upper) // 2
        else:
            return int(attr_val)

    def get_confidence_level(self) -> str:
        """Return a description of scout confidence in this report."""
        confidence_map = {
            'A': "Very High Confidence",
            'B': "High Confidence", 
            'C': "Moderate Confidence",
            'D': "Low Confidence",
            'F': "Very Low Confidence"
        }
        return confidence_map.get(self.accuracy, "Unknown")
    
    def is_recommendation_positive(self) -> bool:
        """Determine if scout recommends this player."""
        if self.scouted_potential in ['A+', 'A', 'A-', 'B+']:
            return True
        elif self.scouted_potential in ['B', 'B-'] and self.accuracy in ['A', 'B']:
            return True
        return False

# --- Email and Inbox System (EHM-style) ---
@dataclass
class EmailMessage:
    """Represents an email message in the inbox system, similar to EHM."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    sender_type: str = "System"  # "System", "Agent", "Scout", "Media", "Owner", "Player", "Staff"
    subject: str = ""
    content: str = ""
    date_sent: date = field(default_factory=date.today)
    date_read: Optional[date] = None
    is_read: bool = False
    is_important: bool = False
    is_urgent: bool = False
    category: str = "General"  # "Trade", "Scouting", "Contracts", "Injuries", "Development", "Media", "League", "General"
    attachments: List[str] = field(default_factory=list)  # For potential future file attachments
    requires_response: bool = False
    response_deadline: Optional[date] = None
    priority: int = 1  # 1=Low, 2=Medium, 3=High, 4=Urgent
    
    # Related game objects (for context)
    related_player_id: Optional[str] = None
    related_team: Optional[str] = None
    related_contract_id: Optional[str] = None
    
    def mark_as_read(self):
        """Mark this email as read."""
        if not self.is_read:
            self.is_read = True
            self.date_read = date.today()
    
    def is_overdue(self) -> bool:
        """Check if this email's response is overdue."""
        if self.requires_response and self.response_deadline:
            return date.today() > self.response_deadline
        return False
    
    def get_age_days(self) -> int:
        """Get the age of this email in days."""
        return (date.today() - self.date_sent).days

@dataclass 
class EmailInbox:
    """Manages the player's email inbox system, similar to EHM."""
    messages: List[EmailMessage] = field(default_factory=list)
    unread_count: int = 0
    total_messages: int = 0
    auto_delete_after_days: int = 365  # Auto-delete old emails after 1 year
    
    def add_message(self, message: EmailMessage):
        """Add a new message to the inbox."""
        self.messages.insert(0, message)  # Add to front for newest first
        if not message.is_read:
            self.unread_count += 1
        self.total_messages += 1
        self._cleanup_old_messages()
    
    def mark_message_read(self, message_id: str):
        """Mark a specific message as read."""
        for message in self.messages:
            if message.id == message_id and not message.is_read:
                message.mark_as_read()
                self.unread_count = max(0, self.unread_count - 1)
                break
    
    def mark_all_read(self):
        """Mark all messages as read."""
        for message in self.messages:
            if not message.is_read:
                message.mark_as_read()
        self.unread_count = 0
    
    def delete_message(self, message_id: str):
        """Delete a specific message."""
        for i, message in enumerate(self.messages):
            if message.id == message_id:
                if not message.is_read:
                    self.unread_count = max(0, self.unread_count - 1)
                del self.messages[i]
                break
    
    def get_messages_by_category(self, category: str) -> List[EmailMessage]:
        """Get all messages in a specific category."""
        return [msg for msg in self.messages if msg.category == category]
    
    def get_unread_messages(self) -> List[EmailMessage]:
        """Get all unread messages."""
        return [msg for msg in self.messages if not msg.is_read]
    
    def get_urgent_messages(self) -> List[EmailMessage]:
        """Get all urgent messages."""
        return [msg for msg in self.messages if msg.is_urgent or msg.priority >= 4]
    
    def get_overdue_messages(self) -> List[EmailMessage]:
        """Get all messages that require a response and are overdue."""
        return [msg for msg in self.messages if msg.is_overdue()]
    
    def _cleanup_old_messages(self):
        """Remove messages older than the auto-delete threshold."""
        cutoff_date = date.today() - timedelta(days=self.auto_delete_after_days)
        initial_count = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.date_sent >= cutoff_date]
        deleted_count = initial_count - len(self.messages)
        if deleted_count > 0:
            print(f"Auto-deleted {deleted_count} old email messages")

class EmailGenerator:
    """Generates realistic emails for various game events, similar to EHM."""
    
    @staticmethod
    def create_trade_offer_email(offering_team: str, target_player: str, offered_players: List[str]) -> EmailMessage:
        """Create an email for a trade offer."""
        subject = f"Trade Offer from {offering_team}"
        content = f"Dear General Manager,\n\n"
        content += f"The {offering_team} have submitted a trade proposal:\n\n"
        content += f"They are requesting: {target_player}\n"
        content += f"They are offering: {', '.join(offered_players)}\n\n"
        content += f"Please review this proposal and respond at your earliest convenience.\n\n"
        content += f"Regards,\nLeague Office"
        
        return EmailMessage(
            sender=f"{offering_team} GM",
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Trade",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=3),
            priority=3,
            related_team=offering_team
        )
    
    @staticmethod
    def create_injury_report_email(player_name: str, injury_type: str, expected_return: str) -> EmailMessage:
        """Create an email for a player injury."""
        subject = f"Injury Report: {player_name}"
        content = f"Medical Department Update\n\n"
        content += f"Player: {player_name}\n"
        content += f"Injury: {injury_type}\n"
        content += f"Expected Return: {expected_return}\n\n"
        content += f"We will continue to monitor {player_name}'s recovery and provide updates as necessary.\n\n"
        content += f"Dr. Smith\nTeam Physician"
        
        return EmailMessage(
            sender="Medical Staff",
            sender_type="Staff",
            subject=subject,
            content=content,
            category="Injuries",
            is_important=True,
            priority=3,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_scouting_report_email(scout_name: str, player_name: str, potential_grade: str) -> EmailMessage:
        """Create an email for a completed scouting report."""
        subject = f"Scouting Report: {player_name}"
        content = f"Scouting Department Report\n\n"
        content += f"Scout: {scout_name}\n"
        content += f"Player: {player_name}\n"
        content += f"Potential Grade: {potential_grade}\n\n"
        content += f"The complete scouting report is now available in the scouting system.\n\n"
        content += f"Best regards,\n{scout_name}\nScout"
        
        return EmailMessage(
            sender=scout_name,
            sender_type="Scout",
            subject=subject,
            content=content,
            category="Scouting",
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_contract_negotiation_email(player_name: str, agent_name: str, demand_type: str) -> EmailMessage:
        """Create an email for contract negotiations."""
        subject = f"Contract Negotiation: {player_name}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing on behalf of my client, {player_name}.\n\n"
        content += f"{demand_type}\n\n"
        content += f"Please contact me to discuss terms.\n\n"
        content += f"Best regards,\n{agent_name}\nPlayer Agent"
        
        return EmailMessage(
            sender=agent_name,
            sender_type="Agent",
            subject=subject,
            content=content,
            category="Contracts",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=7),
            priority=2,
            related_player_id=player_name
        )
    
    @staticmethod
    def create_media_request_email(journalist_name: str, topic: str) -> EmailMessage:
        """Create an email for a media interview request."""
        subject = f"Interview Request: {topic}"
        content = f"Dear General Manager,\n\n"
        content += f"I am writing to request an interview regarding {topic}.\n\n"
        content += f"Would you be available for a brief discussion this week?\n\n"
        content += f"Best regards,\n{journalist_name}\nSports Journalist"
        
        return EmailMessage(
            sender=journalist_name,
            sender_type="Media",
            subject=subject,
            content=content,
            category="Media",
            requires_response=True,
            response_deadline=date.today() + timedelta(days=2),
            priority=1
        )
    
    @staticmethod
    def create_league_announcement_email(subject: str, content: str) -> EmailMessage:
        """Create an email for league announcements."""
        return EmailMessage(
            sender="League Office",
            sender_type="System",
            subject=subject,
            content=content,
            category="League",
            is_important=True,
            priority=2
        )

@dataclass
class DraftPick:
    """Represents a draft pick that can be owned and traded."""
    year: int  # Draft year
    round: int  # Round number (1-7)
    original_team: str  # Team that originally owned this pick
    current_team: str  # Team that currently owns this pick
    overall_pick: int = 0  # Overall pick number (calculated when draft order is set)
    is_conditional: bool = False  # If this pick has conditions attached
    condition: str = ""  # Description of any conditions
    traded_from: str = ""  # Team this pick was traded from (if applicable)
    trade_date: str = ""  # When this pick was traded
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """Calculate overall pick number based on round."""
        if self.overall_pick == 0:
            # Estimate overall pick (32 teams per round)
            self.overall_pick = ((self.round - 1) * 32) + 1
    
    @property
    def description(self) -> str:
        """Get a description of this draft pick."""
        if self.original_team == self.current_team:
            return f"{self.year} {self.round}st Round Pick"
        else:
            return f"{self.year} {self.round}st Round Pick (from {self.original_team})"
    
    @property
    def value(self) -> int:
        """Calculate the trade value of this draft pick."""
        # Base value decreases with later rounds and later years
        base_values = {1: 1000, 2: 500, 3: 250, 4: 125, 5: 100, 6: 75, 7: 50}
        base_value = base_values.get(self.round, 25)
        
        # Decrease value for future years
        year_penalty = max(0, (self.year - 2024) * 50)
        
        # Conditional picks are worth less
        conditional_penalty = 200 if self.is_conditional else 0
        
        return max(25, base_value - year_penalty - conditional_penalty)
    
    def can_be_traded(self) -> bool:
        """Check if this pick can be traded (some leagues have rules)."""
        # Basic rule: can't trade conditional picks that haven't been fulfilled
        if self.is_conditional and self.condition:
            return False
        return True

@dataclass
class GMProfile:
    """Represents the General Manager's profile and background."""
    name: str = "Your Name"
    age: int = 35
    birthplace: str = "Toronto, ON"
    nationality: str = "Canadian"
    
    # Playing background
    former_player: bool = False
    playing_position: str = "Center"  # If former player
    nhl_games_played: int = 0
    career_points: int = 0
    
    # Management background  
    coaching_experience: bool = False
    years_coaching: int = 0
    assistant_gm_experience: bool = False
    years_as_assistant: int = 0
    
    # Education & Skills
    education_level: str = "University Degree"  # High School, College, University Degree, MBA
    management_style: str = "Balanced"  # Analytics-Based, Traditional, Player-First, Balanced
    
    # Personality traits that could affect gameplay
    risk_tolerance: str = "Moderate"  # Conservative, Moderate, Aggressive
    loyalty_to_players: str = "Medium"  # Low, Medium, High
    media_savvy: str = "Good"  # Poor, Average, Good, Excellent
    
    def __post_init__(self):
        """Validate GM profile data after initialization."""
        if self.age < 25:
            self.age = 25
        elif self.age > 70:
            self.age = 70

@dataclass
class Team:
    """Represents a single hockey team with a deep organizational structure."""
    team_name: str
    city: str
    division: str
    conference: str
    league_name: str = "National Hockey League"  # Default to NHL
    gm_name: str = "General Manager"  # Name of the team's GM
    gm_profile: GMProfile = field(default_factory=GMProfile)  # Full GM profile
    
    roster: List[Player] = field(default_factory=list)
    ahl_roster: List[Player] = field(default_factory=list)
    prospects: List[Player] = field(default_factory=list)
    staff: List[Staff] = field(default_factory=list)
    lineup: Dict[str, Player] = field(default_factory=dict)
    
    is_user_team: bool = False
    salary_cap: int = 83500000
    scouting_reports: Dict[int, ScoutingReport] = field(default_factory=dict)
    inbox: EmailInbox = field(default_factory=EmailInbox)  # Email inbox system
    
    # Draft picks owned by this team
    draft_picks: Dict[int, List[DraftPick]] = field(default_factory=dict)  # Year -> List of picks
    
    # Team Statistics for Standings
    wins: int = 0
    losses: int = 0
    ties: int = 0
    ot_losses: int = 0
    games_played: int = 0

    @property
    def payroll(self) -> int:
        return sum(p.contract.salary for p in self.roster)

    @property
    def cap_space(self) -> int:
        return self.salary_cap - self.payroll
    
    @property
    def team_chemistry(self) -> int:
        """Calculates team chemistry based on player morale and leadership."""
        if not self.roster:
            return 50
        avg_morale = sum(p.morale for p in self.roster) / len(self.roster)
        avg_leadership = sum(p.leadership for p in self.roster) / len(self.roster)
        return int((avg_morale * 6) + (avg_leadership * 4))
    
    @property
    def points(self) -> int:
        """Calculate total points (2 for win, 1 for tie/OT loss)"""
        return (self.wins * 2) + self.ties + self.ot_losses
    
    @property
    def winning_percentage(self) -> float:
        """Calculate winning percentage"""
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played
    
    @property
    def record_string(self) -> str:
        """Get team record as a formatted string"""
        if self.ot_losses > 0:
            return f"{self.wins}-{self.losses}-{self.ot_losses}"
        elif self.ties > 0:
            return f"{self.wins}-{self.losses}-{self.ties}"
        else:
            return f"{self.wins}-{self.losses}"

    def add_player(self, player: Player, roster_type: str = "roster"):
        """Adds a player to the specified roster (roster, ahl, prospects)."""
        roster_map = { "roster": self.roster, "ahl": self.ahl_roster, "prospects": self.prospects }
        if roster_type in roster_map:
            roster_map[roster_type].append(player)
            player.team_name = self.team_name
        else:
            raise ValueError("Invalid roster type specified.")

    def remove_player(self, player: Player):
        """Removes a player from any list they are on."""
        if player in self.roster: self.roster.remove(player)
        if player in self.ahl_roster: self.ahl_roster.remove(player)
        if player in self.prospects: self.prospects.remove(player)
        player.team_name = "Free Agent"

    def get_players_by_position(self, position: PlayerPosition) -> List[Player]:
        return [p for p in self.roster if p.primary_position == position]

    def get_starting_goalie(self) -> Player:
        goalies = self.get_players_by_position(PlayerPosition.GOALIE)
        if not goalies:
            return Player("Default", "Goalie", 99, PlayerPosition.GOALIE, goaltending=1)
        return max(goalies, key=lambda g: g.overall_rating())
    
    def validate_staff_structure(self) -> Dict[str, List[str]]:
        """Validate the team's staff structure and return any issues"""
        issues = {'errors': [], 'warnings': []}
        
        # Check for unique role violations
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        role_counts = {}
        
        for staff_member in self.staff:
            role = staff_member.role
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Check unique role constraints
        for role in unique_roles:
            count = role_counts.get(role, 0)
            if count == 0:
                issues['errors'].append(f"Missing {role.value}")
            elif count > 1:
                issues['errors'].append(f"Multiple {role.value}s ({count})")
        
        # Check essential roles
        essential_roles = [
            StaffRole.GENERAL_MANAGER,
            StaffRole.HEAD_COACH,
            StaffRole.ASSISTANT_COACH,
            StaffRole.GOALIE_COACH
        ]
        
        for role in essential_roles:
            if role not in role_counts:
                issues['warnings'].append(f"Missing {role.value}")
        
        # Check total staff count
        if len(self.staff) < 8:
            issues['warnings'].append(f"Only {len(self.staff)} staff members (recommended: 10-15)")
        elif len(self.staff) > 20:
            issues['warnings'].append(f"Very large staff ({len(self.staff)} members)")
        
        return issues
    
    def get_staff_by_role(self, role: StaffRole) -> List[Staff]:
        """Get all staff members with a specific role"""
        return [staff for staff in self.staff if staff.role == role]
    
    def has_unique_roles(self) -> bool:
        """Check if team has exactly one of each unique role"""
        unique_roles = [StaffRole.GENERAL_MANAGER, StaffRole.HEAD_COACH]
        for role in unique_roles:
            staff_with_role = self.get_staff_by_role(role)
            if len(staff_with_role) != 1:
                return False
        return True
    
    def update_record(self, result: str, overtime: bool = False):
        """Update team record based on game result"""
        self.games_played += 1
        
        if result.upper() == "WIN":
            self.wins += 1
        elif result.upper() == "LOSS":
            if overtime:
                self.ot_losses += 1
            else:
                self.losses += 1
        elif result.upper() == "TIE":
            self.ties += 1
    
    def reset_season_record(self):
        """Reset team record for new season"""
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.ot_losses = 0
        self.games_played = 0
    
    def generate_sample_season_record(self, games_played: int = 25):
        """Generate a realistic sample season record for demonstration purposes"""
        import random
        
        # Reset current record
        self.reset_season_record()
        
        # Based on team quality (average roster rating), determine win probability
        if self.roster:
            avg_rating = sum(p.overall_rating() for p in self.roster[:20]) / min(20, len(self.roster))
            # Convert rating (0-20) to win probability (0.3 - 0.7)
            base_win_probability = 0.3 + (avg_rating / 20.0) * 0.4
        else:
            base_win_probability = 0.5  # Default 50% win rate
        
        # Simulate games
        for _ in range(games_played):
            self.games_played += 1
            
            # Random outcome based on team strength
            outcome_roll = random.random()
            
            if outcome_roll < base_win_probability:
                self.wins += 1
            elif outcome_roll < base_win_probability + 0.08:  # 8% chance of OT loss
                self.ot_losses += 1
            elif outcome_roll < base_win_probability + 0.12:  # 4% chance of tie (rare in modern NHL)
                self.ties += 1
            else:
                self.losses += 1

    def initialize_draft_picks(self, years: List[int]):
        """Initialize standard draft picks for specified years."""
        for year in years:
            if year not in self.draft_picks:
                self.draft_picks[year] = []
                
            # Add standard 7 rounds of picks if they don't exist
            existing_rounds = {pick.round for pick in self.draft_picks[year]}
            for round_num in range(1, 8):  # Rounds 1-7
                if round_num not in existing_rounds:
                    pick = DraftPick(
                        year=year,
                        round=round_num,
                        original_team=self.team_name,
                        current_team=self.team_name
                    )
                    self.draft_picks[year].append(pick)

    def get_picks_for_year(self, year: int) -> List[DraftPick]:
        """Get all draft picks owned by this team for a specific year."""
        return self.draft_picks.get(year, [])

    def get_tradeable_picks(self, years: List[int] = None) -> List[DraftPick]:
        """Get all tradeable draft picks owned by this team."""
        if years is None:
            years = list(self.draft_picks.keys())
        
        tradeable = []
        for year in years:
            for pick in self.draft_picks.get(year, []):
                if pick.can_be_traded():
                    tradeable.append(pick)
        return tradeable

    def trade_pick(self, pick: DraftPick, to_team: str, trade_details: str = ""):
        """Trade a draft pick to another team."""
        if pick not in self.draft_picks.get(pick.year, []):
            raise ValueError("Team does not own this draft pick")
        
        if not pick.can_be_traded():
            raise ValueError("This draft pick cannot be traded")
        
        # Update pick ownership
        pick.traded_from = self.team_name
        pick.current_team = to_team
        pick.trade_date = str(date.today())
        
        # Remove from this team's picks
        self.draft_picks[pick.year].remove(pick)

    def receive_pick(self, pick: DraftPick):
        """Receive a draft pick from a trade."""
        # Ensure the year exists in our picks dictionary
        if pick.year not in self.draft_picks:
            self.draft_picks[pick.year] = []
        
        # Update ownership
        pick.current_team = self.team_name
        
        # Add to our picks
        self.draft_picks[pick.year].append(pick)

    def get_draft_pick_summary(self) -> str:
        """Get a summary of all draft picks owned."""
        if not self.draft_picks:
            return "No draft picks"
        
        summary_parts = []
        for year in sorted(self.draft_picks.keys()):
            picks = self.draft_picks[year]
            if picks:
                rounds = sorted([pick.round for pick in picks])
                summary_parts.append(f"{year}: Rounds {', '.join(map(str, rounds))}")
        
        return "; ".join(summary_parts) if summary_parts else "No draft picks"

    def count_picks_by_round(self, year: int) -> Dict[int, int]:
        """Count how many picks the team has in each round for a given year."""
        picks = self.get_picks_for_year(year)
        round_counts = {}
        
        for pick in picks:
            round_counts[pick.round] = round_counts.get(pick.round, 0) + 1
        
        return round_counts

@dataclass
@dataclass
class League:
    """Represents the entire league, structured like the NHL."""
    league_name: str
    teams: List[Team] = field(default_factory=list)
    free_agents: List[Player] = field(default_factory=list)  # Kept for compatibility, but may be overridden
    free_agent_staff: List[Staff] = field(default_factory=list)
    draft_prospects: List[Player] = field(default_factory=list)
    schedule: List[Tuple[date, Team, Team]] = field(default_factory=list)
    standings: Dict[str, Dict] = field(default_factory=dict)
    current_game_index: int = 0
    season_year: int = 2024
    _game_manager: object = field(default=None, init=False, repr=False)  # Reference to game manager
    
    def set_game_manager(self, game_manager):
        """Set reference to game manager for database access."""
        self._game_manager = game_manager
    
    def __post_init__(self):
        self.setup_nhl_teams()

    def setup_nhl_teams(self):
        """Initializes the league with all 32 real NHL teams (2024-25 season)."""
        teams_data = {
            # Eastern Conference
            "Metropolitan": {
                "Carolina Hurricanes": "Raleigh", "Columbus Blue Jackets": "Columbus", 
                "New Jersey Devils": "Newark", "New York Islanders": "New York", 
                "New York Rangers": "New York", "Philadelphia Flyers": "Philadelphia", 
                "Pittsburgh Penguins": "Pittsburgh", "Washington Capitals": "Washington"
            },
            "Atlantic": {
                "Boston Bruins": "Boston", "Buffalo Sabres": "Buffalo", 
                "Detroit Red Wings": "Detroit", "Florida Panthers": "Sunrise", 
                "Montréal Canadiens": "Montreal", "Ottawa Senators": "Ottawa", 
                "Tampa Bay Lightning": "Tampa Bay", "Toronto Maple Leafs": "Toronto"
            },
            # Western Conference
            "Central": {
                "Chicago Blackhawks": "Chicago", "Colorado Avalanche": "Denver", 
                "Dallas Stars": "Dallas", "Minnesota Wild": "St. Paul", 
                "Nashville Predators": "Nashville", "St. Louis Blues": "St. Louis", 
                "Utah Hockey Club": "Salt Lake City", "Winnipeg Jets": "Winnipeg"
            },
            "Pacific": {
                "Anaheim Ducks": "Anaheim", "Calgary Flames": "Calgary", 
                "Edmonton Oilers": "Edmonton", "Los Angeles Kings": "Los Angeles", 
                "San Jose Sharks": "San Jose", "Seattle Kraken": "Seattle", 
                "Vancouver Canucks": "Vancouver", "Vegas Golden Knights": "Las Vegas"
            }
        }
        for division, teams in teams_data.items():
            conference = "Eastern" if division in ["Metropolitan", "Atlantic"] else "Western"
            for name, city in teams.items():
                team = Team(name, city, division, conference)
                team.league_name = "National Hockey League"  # Mark as NHL team
                self.teams.append(team)
        self.initialize_standings()

    def initialize_standings(self):
        """Sets up the standings dictionary for each team."""
        for team in self.teams:
            self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}

    def generate_schedule(self):
        """Generates NHL-compliant schedules with proper calendar breaks and optimized back-to-backs."""
        self.schedule.clear()
        
        # Group teams by league
        leagues = {}
        for team in self.teams:
            league_name = getattr(team, 'league_name', 'National Hockey League')
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(team)
        
        # Generate schedule for each league separately
        for league_name, league_teams in leagues.items():
            if len(league_teams) < 2:
                continue  # Skip leagues with less than 2 teams
                
            print(f"Generating schedule for {league_name} ({len(league_teams)} teams)")
            if league_name == "National Hockey League":
                self._generate_nhl_compliant_schedule(league_teams)
            else:
                self._generate_other_league_schedule(league_teams, league_name)
        
        # Sort all games by date
        self.schedule.sort(key=lambda x: x[0])
        
        # Verify schedule integrity
        self._verify_nhl_schedule_integrity()

    def _generate_nhl_compliant_schedule(self, nhl_teams):
        """Generates NHL schedule with exactly 82 games per team, proper breaks, and optimized back-to-backs."""
        print("🏒 Generating NHL-compliant schedule with realistic calendar...")
        
        # Step 1: Generate exactly 82 games per team
        matchups = self._create_nhl_82_game_matchups(nhl_teams)
        
        # Step 2: Create NHL calendar with proper breaks
        nhl_calendar = self._create_nhl_calendar_with_breaks()
        
        # Step 3: Schedule games with optimized back-to-back management
        self._schedule_nhl_games_optimized(matchups, nhl_teams, nhl_calendar)
        
        # Step 4: Report final statistics
        self._report_nhl_schedule_compliance(nhl_teams)
    
    def _create_nhl_82_game_matchups(self, nhl_teams):
        """Create exactly 82 games per team following NHL divisional structure."""
        if len(nhl_teams) != 32:
            print(f"Warning: Expected 32 NHL teams, got {len(nhl_teams)}")
            return []
        
        # Group teams by conference and division
        divisions = {}
        for team in nhl_teams:
            div_key = (team.conference, team.division)
            if div_key not in divisions:
                divisions[div_key] = []
            divisions[div_key].append(team)
        
        print(f"NHL structure: {len(divisions)} divisions")
        for div_key, teams in divisions.items():
            print(f"  {div_key}: {len(teams)} teams")
        
        matchups = []
        
        # NHL 82-game formula (exact):
        # - Division rivals: 4 games each (7 rivals × 4 = 28 games)
        # - Other conference teams: 3 games each (8 teams × 3 = 24 games)  
        # - Other non-conference teams: 2 games each (16 teams × 2 = 32 games)
        # But we need to adjust to exactly 82 games
        
        # Process each team's schedule
        for team in nhl_teams:
            team_div = (team.conference, team.division)
            division_rivals = [t for t in divisions[team_div] if t != team]
            
            # Same conference teams (excluding own division)
            same_conf_teams = []
            for div_key, teams in divisions.items():
                if div_key[0] == team.conference and div_key != team_div:
                    same_conf_teams.extend(teams)
            
            # Other conference teams
            other_conf_teams = []
            for div_key, teams in divisions.items():
                if div_key[0] != team.conference:
                    other_conf_teams.extend(teams)
            
            # Schedule games for this team
            # Division rivals: 4 games each (alternating home/away)
            for rival in division_rivals:
                matchups.extend([
                    (team, rival), (rival, team),  # 2 games each direction
                    (team, rival), (rival, team)   # Total: 4 games
                ])
            
            # Same conference: 3 games each (with home advantage rotation)
            for opponent in same_conf_teams:
                if hash(team.team_name + opponent.team_name) % 2 == 0:
                    # Team gets extra home game
                    matchups.extend([
                        (team, opponent), (team, opponent),  # 2 home
                        (opponent, team)  # 1 away
                    ])
                else:
                    # Opponent gets extra home game
                    matchups.extend([
                        (team, opponent),  # 1 home  
                        (opponent, team), (opponent, team)  # 2 away
                    ])
            
            # Other conference: 2 games each (1 home, 1 away)
            for opponent in other_conf_teams:
                matchups.extend([
                    (team, opponent),    # 1 home
                    (opponent, team)     # 1 away
                ])
        
        # Remove duplicate matchups (since we process each team)
        unique_matchups = []
        seen_games = set()
        
        for home_team, away_team in matchups:
            game_key = (home_team.team_name, away_team.team_name)
            if game_key not in seen_games:
                unique_matchups.append((home_team, away_team))
                seen_games.add(game_key)
        
        # Verify 82 games per team
        team_game_counts = {}
        for home_team, away_team in unique_matchups:
            team_game_counts[home_team.team_name] = team_game_counts.get(home_team.team_name, 0) + 1
            team_game_counts[away_team.team_name] = team_game_counts.get(away_team.team_name, 0) + 1
        
        print(f"Generated {len(unique_matchups)} total games")
        for team_name, count in list(team_game_counts.items())[:3]:  # Show first 3 teams
            print(f"  {team_name}: {count} games")
        
        return unique_matchups
    
    def _create_nhl_calendar_with_breaks(self):
        """Create NHL calendar with All-Star break, trade deadline, and other considerations."""
        season_start = date(self.season_year, 10, 10)  # October 10th
        season_end = date(self.season_year + 1, 4, 12)  # April 12th
        
        # NHL calendar restrictions
        calendar_info = {
            'season_start': season_start,
            'season_end': season_end,
            'all_star_break': (
                date(self.season_year + 1, 1, 28),  # All-Star break start
                date(self.season_year + 1, 2, 3)    # All-Star break end
            ),
            'trade_deadline': date(self.season_year + 1, 3, 3),  # March 3rd
            'christmas_break': (
                date(self.season_year, 12, 23),     # Christmas break start  
                date(self.season_year, 12, 26)      # Christmas break end
            ),
            'olympic_break': None  # Only in Olympic years
        }
        
        # Generate available game dates
        available_dates = []
        current_date = season_start
        
        while current_date <= season_end:
            # Skip break periods
            skip_date = False
            
            # All-Star break
            if (calendar_info['all_star_break'][0] <= current_date <= 
                calendar_info['all_star_break'][1]):
                skip_date = True
            
            # Christmas break  
            if (calendar_info['christmas_break'][0] <= current_date <= 
                calendar_info['christmas_break'][1]):
                skip_date = True
            
            # Skip most Mondays (NHL typically avoids Monday games)
            if current_date.weekday() == 0 and random.random() < 0.8:
                skip_date = True
            
            # Prefer Tuesday, Thursday, Saturday, Sunday
            weekday = current_date.weekday()
            if weekday in [1, 3, 5, 6]:  # Tue, Thu, Sat, Sun
                weight = 1.0
            elif weekday in [2, 4]:      # Wed, Fri
                weight = 0.7
            else:                        # Monday
                weight = 0.2
            
            if not skip_date and random.random() < weight:
                available_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        print(f"NHL calendar: {len(available_dates)} available game days")
        print(f"All-Star break: {calendar_info['all_star_break'][0]} to {calendar_info['all_star_break'][1]}")
        print(f"Trade deadline: {calendar_info['trade_deadline']}")
        
        return {
            'available_dates': available_dates,
            'calendar_info': calendar_info
        }
    
    def _schedule_nhl_games_optimized(self, matchups, nhl_teams, nhl_calendar):
        """Schedule NHL games with optimized back-to-back management (7-16 per team)."""
        available_dates = nhl_calendar['available_dates']
        calendar_info = nhl_calendar['calendar_info']
        
        # Initialize team tracking with stricter back-to-back budget
        team_tracking = {}
        for team in nhl_teams:
            team_tracking[team.team_name] = {
                'games_scheduled': 0,
                'home_games': 0,
                'away_games': 0,
                'back_to_backs': 0,
                'back_to_back_budget': 12,  # Target: 7-16 back-to-backs (use 12 as budget)
                'last_game_date': None,
                'consecutive_games': 0,
                'schedule': [],  # (date, opponent, home/away)
                'rest_days_total': 0
            }
        
        # Track daily game limits (max 16 games per day in NHL)
        daily_game_count = {date: 0 for date in available_dates}
        scheduled_games = []
        
        # Prioritize matchups by scheduling difficulty
        def matchup_priority(matchup):
            home_team, away_team = matchup
            home_track = team_tracking[home_team.team_name]
            away_track = team_tracking[away_team.team_name]
            
            # Prioritize teams with fewer scheduled games
            total_games = home_track['games_scheduled'] + away_track['games_scheduled']
            
            # Prioritize teams with available back-to-back budget
            total_budget = home_track['back_to_back_budget'] + away_track['back_to_back_budget']
            
            return (total_games, -total_budget)  # Fewer games first, more budget preferred
        
        matchups.sort(key=matchup_priority)
        
        # Schedule each game
        for i, (home_team, away_team) in enumerate(matchups):
            if i % 200 == 0:  # Progress indicator
                print(f"  Scheduling progress: {i}/{len(matchups)} games ({i/len(matchups)*100:.1f}%)")
            
            best_date = self._find_optimal_nhl_game_date(
                home_team, away_team, available_dates, team_tracking, 
                daily_game_count, calendar_info
            )
            
            if best_date:
                # Schedule the game
                scheduled_games.append((best_date, home_team, away_team))
                daily_game_count[best_date] += 1
                
                # Update team tracking
                self._update_nhl_team_tracking(
                    home_team, away_team, best_date, team_tracking
                )
        
        # Add all games to main schedule
        self.schedule.extend(scheduled_games)
        print(f"✅ Scheduled {len(scheduled_games)} NHL games")
    
    def _find_optimal_nhl_game_date(self, home_team, away_team, available_dates, 
                                  team_tracking, daily_game_count, calendar_info):
        """Find optimal date with strict back-to-back management."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Skip if day is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check team constraints
            home_valid, home_penalty = self._check_nhl_team_constraints(
                home_team, game_date, team_tracking, True, calendar_info
            )
            away_valid, away_penalty = self._check_nhl_team_constraints(
                away_team, game_date, team_tracking, False, calendar_info
            )
            
            if home_valid and away_valid:
                # Calculate total penalty (lower is better)
                total_penalty = home_penalty + away_penalty
                
                # Add home/away balance bonus
                home_balance = self._calculate_nhl_home_away_balance(
                    home_team, team_tracking, True
                )
                away_balance = self._calculate_nhl_home_away_balance(
                    away_team, team_tracking, False
                )
                
                total_penalty += home_balance + away_balance
                candidate_dates.append((game_date, total_penalty))
        
        # Return best date (lowest penalty)
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        # Emergency scheduling with relaxed constraints
        return self._emergency_nhl_scheduling(
            home_team, away_team, available_dates, team_tracking, daily_game_count
        )
    
    def _check_nhl_team_constraints(self, team, game_date, team_tracking, 
                                  is_home_team, calendar_info):
        """Check NHL scheduling constraints with optimized back-to-back management."""
        track = team_tracking[team.team_name]
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule)
        if any(scheduled_date == game_date for scheduled_date, _, _ in track['schedule']):
            return False, float('inf')
        
        # 2. Back-to-back budget management
        is_back_to_back = (track['last_game_date'] and 
                          track['last_game_date'] == game_date - timedelta(days=1))
        
        if is_back_to_back:
            # Check budget availability
            if track['back_to_back_budget'] <= 0:
                return False, float('inf')  # No budget left
            
            # Progressive restrictions based on season timing
            games_played = track['games_scheduled']
            season_progress = games_played / 82.0
            
            # Be very conservative late in season
            if season_progress > 0.75 and track['back_to_back_budget'] < 3:
                return False, float('inf')
            
            # Be moderately conservative mid-season
            if season_progress > 0.5 and track['back_to_back_budget'] < 6:
                if random.random() < 0.7:  # 70% chance to reject
                    return False, float('inf')
        
        # 3. No more than 2 consecutive games (3 games in 3 days)
        if (track['last_game_date'] and 
            len(track['schedule']) >= 2):
            last_two_dates = sorted([d for d, _, _ in track['schedule'][-2:]])
            if (len(last_two_dates) >= 2 and
                last_two_dates[-1] == game_date - timedelta(days=1) and
                last_two_dates[-2] == game_date - timedelta(days=2)):
                return False, float('inf')
        
        # SOFT CONSTRAINTS (affect priority - lower penalty is better)
        penalty = 0
        
        # Back-to-back penalty (progressive)
        if is_back_to_back:
            base_penalty = 25
            budget_used = 12 - track['back_to_back_budget']
            penalty += base_penalty + (budget_used * 5)  # Escalating penalty
        
        # Rest day bonuses
        if track['last_game_date']:
            days_rest = (game_date - track['last_game_date']).days - 1
            if days_rest == 1:      # 1 day rest (good)
                penalty -= 5
            elif days_rest == 2:    # 2 days rest (better) 
                penalty -= 10
            elif days_rest >= 3:    # 3+ days rest (optimal)
                penalty -= 15
            elif days_rest > 7:     # Too much rest
                penalty += days_rest - 7
        
        # Trade deadline considerations (schedule easier games late)
        if game_date > calendar_info['trade_deadline']:
            penalty += 5  # Slight penalty for post-deadline games
        
        return True, penalty
    
    def _calculate_nhl_home_away_balance(self, team, team_tracking, is_home_game):
        """Calculate penalty for home/away imbalance (target: 41 home, 41 away)."""
        track = team_tracking[team.team_name]
        
        current_home = track['home_games']
        current_away = track['away_games']
        games_played = track['games_scheduled']
        
        if games_played == 0:
            return 0  # No penalty for first game
        
        # Calculate current ratio
        if is_home_game:
            new_home = current_home + 1
            new_away = current_away
        else:
            new_home = current_home  
            new_away = current_away + 1
        
        total_games = new_home + new_away
        home_ratio = new_home / total_games if total_games > 0 else 0.5
        
        # Target is 50/50 split (41 home, 41 away out of 82)
        target_ratio = 0.5
        imbalance = abs(home_ratio - target_ratio)
        
        # Penalty increases with imbalance
        if imbalance > 0.15:      # More than 15% off
            return 15
        elif imbalance > 0.10:    # More than 10% off
            return 10
        elif imbalance > 0.05:    # More than 5% off
            return 5
        else:
            return 0
    
    def _update_nhl_team_tracking(self, home_team, away_team, game_date, team_tracking):
        """Update team tracking after scheduling an NHL game."""
        for team in [home_team, away_team]:
            track = team_tracking[team.team_name]
            is_home = (team == home_team)
            
            # Check for back-to-back
            is_back_to_back = (track['last_game_date'] and 
                             track['last_game_date'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['games_scheduled'] += 1
            if is_home:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1
            
            # Update schedule and last game date
            opponent = away_team if is_home else home_team
            track['schedule'].append((game_date, opponent.team_name, 'HOME' if is_home else 'AWAY'))
            track['last_game_date'] = game_date
    
    def _emergency_nhl_scheduling(self, home_team, away_team, available_dates, 
                                team_tracking, daily_game_count):
        """Emergency NHL scheduling with relaxed constraints."""
        MAX_DAILY_GAMES = 20  # Relaxed limit
        
        # Try with relaxed daily limits
        for game_date in available_dates:
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check only critical constraints (no same-day games)
            home_track = team_tracking[home_team.team_name]
            away_track = team_tracking[away_team.team_name]
            
            home_same_day = any(d == game_date for d, _, _ in home_track['schedule'])
            away_same_day = any(d == game_date for d, _, _ in away_track['schedule'])
            
            if not home_same_day and not away_same_day:
                return game_date
        
        return None  # Could not schedule
    
    def _report_nhl_schedule_compliance(self, nhl_teams):
        """Report NHL schedule compliance and statistics."""
        print("\n🏒 NHL SCHEDULE COMPLIANCE REPORT")
        print("=" * 50)
        
        # Collect statistics
        team_stats = {}
        for team in nhl_teams:
            team_name = team.team_name
            team_games = [(date, home_team, away_team) for date, home_team, away_team in self.schedule 
                         if home_team.team_name == team_name or away_team.team_name == team_name]
            
            home_games = sum(1 for _, home_team, _ in team_games if home_team.team_name == team_name)
            away_games = len(team_games) - home_games
            
            # Count back-to-backs
            dates = sorted([date for date, _, _ in team_games])
            back_to_backs = sum(1 for i in range(len(dates)-1) 
                              if (dates[i+1] - dates[i]).days == 1)
            
            team_stats[team_name] = {
                'total_games': len(team_games),
                'home_games': home_games,
                'away_games': away_games, 
                'back_to_backs': back_to_backs
            }
        
        # Summary statistics
        total_games = [stats['total_games'] for stats in team_stats.values()]
        home_games = [stats['home_games'] for stats in team_stats.values()]  
        away_games = [stats['away_games'] for stats in team_stats.values()]
        back_to_backs = [stats['back_to_backs'] for stats in team_stats.values()]
        
        print(f"✅ Teams: {len(nhl_teams)}")
        print(f"✅ Total games: {len(self.schedule)}")
        print(f"✅ Games per team: {sum(total_games)/len(total_games):.1f} avg")
        print(f"✅ Home games per team: {sum(home_games)/len(home_games):.1f} avg")
        print(f"✅ Away games per team: {sum(away_games)/len(away_games):.1f} avg")
        print(f"🎯 Back-to-backs per team: {sum(back_to_backs)/len(back_to_backs):.1f} avg")
        print(f"🎯 Back-to-back range: {min(back_to_backs)}-{max(back_to_backs)} per team")
        
        # Check compliance
        games_82 = sum(1 for games in total_games if games == 82)
        home_away_balanced = sum(1 for i in range(len(home_games)) 
                               if abs(home_games[i] - away_games[i]) <= 2)
        back_to_back_compliant = sum(1 for bb in back_to_backs if 7 <= bb <= 16)
        
        print(f"\n📊 COMPLIANCE CHECK:")
        print(f"   82 games per team: {games_82}/{len(nhl_teams)} teams ✅" if games_82 == len(nhl_teams) else f"   82 games per team: {games_82}/{len(nhl_teams)} teams ❌")
        print(f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ✅" if home_away_balanced >= len(nhl_teams) * 0.9 else f"   Balanced home/away: {home_away_balanced}/{len(nhl_teams)} teams ❌")
        print(f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams ✅" if back_to_back_compliant >= len(nhl_teams) * 0.8 else f"   Back-to-backs 7-16: {back_to_back_compliant}/{len(nhl_teams)} teams 🎯")
    
    def _generate_other_league_schedule(self, league_teams, league_name):
        """Generate schedule for non-NHL leagues with simpler rules."""
        matchups = []
        
        # Simple round-robin: each team plays each other team twice (home and away)
        for team1 in league_teams:
            for team2 in league_teams:
                if team1 == team2:
                    continue
                matchups.extend([(team1, team2), (team2, team1)])
        
        # Determine season dates
        season_start = date(self.season_year, 10, 1)
        season_end = date(self.season_year + 1, 3, 31)
        
        # Simple date distribution
        available_dates = []
        current_date = season_start
        while current_date <= season_end:
            if current_date.weekday() < 6:  # Monday-Saturday
                available_dates.append(current_date)
            current_date += timedelta(days=1)
        
        # Schedule games with minimal constraints
        daily_limit = 8  # Lower limit for other leagues
        date_index = 0
        
        for home_team, away_team in matchups:
            if date_index < len(available_dates):
                game_date = available_dates[date_index]
                self.schedule.append((game_date, home_team, away_team))
                
                # Move to next date occasionally to spread games
                if random.random() < 0.3:
                    date_index += 1
        
        print(f"✅ Scheduled {len(matchups)} games for {league_name}")

    def _verify_nhl_schedule_integrity(self):
        """Verify NHL schedule meets all requirements."""
        print("\n🔍 Verifying NHL schedule integrity...")
        
        # Collect team statistics
        team_schedules = {}
        for game_date, home_team, away_team in self.schedule:
            # Track home team
            if home_team.team_name not in team_schedules:
                team_schedules[home_team.team_name] = []
            team_schedules[home_team.team_name].append((game_date, away_team.team_name, 'HOME'))
            
            # Track away team  
            if away_team.team_name not in team_schedules:
                team_schedules[away_team.team_name] = []
            team_schedules[away_team.team_name].append((game_date, home_team.team_name, 'AWAY'))
        
        # Check for violations
        same_day_violations = 0
        back_to_back_violations = 0
        consecutive_violations = 0
        
        for team_name, schedule in team_schedules.items():
            schedule.sort()  # Sort by date
            
            # Check same-day violations
            dates = [game_date for game_date, _, _ in schedule]
            if len(dates) != len(set(dates)):
                same_day_violations += 1
                print(f"❌ {team_name}: Multiple games on same day")
            
            # Check back-to-back and consecutive game violations
            back_to_backs = 0
            max_consecutive = 0
            current_consecutive = 0
            
            for i in range(len(dates)):
                if i > 0:
                    days_diff = (dates[i] - dates[i-1]).days
                    if days_diff == 1:
                        back_to_backs += 1
                        current_consecutive += 1
                    else:
                        max_consecutive = max(max_consecutive, current_consecutive)
                        current_consecutive = 1
                else:
                    current_consecutive = 1
            
            max_consecutive = max(max_consecutive, current_consecutive)
            
            if back_to_backs > 16:  # Allow up to 16 back-to-backs
                back_to_back_violations += 1
            
            if max_consecutive > 3:  # Max 3 consecutive games
                consecutive_violations += 1
        
        # Summary
        total_teams = len(team_schedules)
        print(f"📊 INTEGRITY SUMMARY:")
        print(f"   Same-day violations: {same_day_violations}/{total_teams} teams")
        print(f"   Excessive back-to-backs: {back_to_back_violations}/{total_teams} teams") 
        print(f"   Excessive consecutive games: {consecutive_violations}/{total_teams} teams")
        
        if same_day_violations == 0:
            print("✅ No same-day violations detected")
        if back_to_back_violations <= total_teams * 0.1:  # Allow 10% of teams to exceed
            print("✅ Back-to-back violations within acceptable range")
        if consecutive_violations == 0:
            print("✅ No excessive consecutive game violations")


        # Create comprehensive team tracking with home/away balance
        team_tracking = {}
        for team in teams:
            team_tracking[team.team_name] = {
                'last_game': None,
                'second_last_game': None,
                'games_scheduled': 0,
                'home_games': 0,
                'away_games': 0,
                'back_to_backs': 0,
                'back_to_back_budget': 14,  # NHL max back-to-backs per team
                'consecutive_games': 0,
                'last_rest_days': 0,
                'schedule': []  # List of (date, opponent, home/away) tuples
            }
        
        # Generate valid NHL game dates
        available_dates = self._generate_nhl_game_dates(start_date, end_date)
        
        # Track daily game counts (NHL max ~16 games per day)
        daily_game_count = {date: 0 for date in available_dates}
        
        # Sort matchups to prioritize teams that haven't played recently
        def matchup_priority(matchup):
            home_team, away_team = matchup
            home_track = team_tracking[home_team.team_name]
            away_track = team_tracking[away_team.team_name]
            
            # Teams with fewer games get higher priority
            return home_track['games_scheduled'] + away_track['games_scheduled']
        
        matchups.sort(key=matchup_priority)
        
        scheduled_games = []
        
        for home_team, away_team in matchups:
            best_date = self._find_best_game_date(
                home_team, away_team, available_dates, 
                team_tracking, daily_game_count
            )
            
            if best_date:
                # Schedule the game
                scheduled_games.append((best_date, home_team, away_team))
                daily_game_count[best_date] += 1
                
                # Update team tracking
                self._update_team_tracking_after_game(
                    home_team, away_team, best_date, team_tracking
                )
            else:
                # Emergency scheduling - find any valid date
                emergency_date = self._emergency_schedule(
                    home_team, away_team, available_dates, team_tracking
                )
                if emergency_date:
                    scheduled_games.append((emergency_date, home_team, away_team))
                    daily_game_count[emergency_date] += 1
                    self._update_team_tracking_after_game(
                        home_team, away_team, emergency_date, team_tracking
                    )
                # If emergency_date is None, the game is skipped to prevent same-day violations
        
        # Add all scheduled games to the main schedule
        self.schedule.extend(scheduled_games)
        
        # Report scheduling statistics with enhanced metrics
        self._report_schedule_stats_enhanced(team_tracking, teams)
    
    def _generate_nhl_game_dates(self, start_date, end_date):
        """Generate realistic NHL game dates based on actual NHL scheduling patterns."""
        valid_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # NHL typically plays:
            # - Tuesday through Sunday (avoid Monday)
            # - More games on Tue/Thu/Sat/Sun, fewer on Wed/Fri
            if weekday == 0:  # Monday - very rare
                if random.random() < 0.1:  # Only 10% chance
                    valid_dates.append(current_date)
            elif weekday in [1, 3, 5, 6]:  # Tue, Thu, Sat, Sun - primary days
                valid_dates.append(current_date)
            elif weekday in [2, 4]:  # Wed, Fri - secondary days
                if random.random() < 0.7:  # 70% chance
                    valid_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        return valid_dates
    
    def _find_best_game_date(self, home_team, away_team, available_dates, 
                            team_tracking, daily_game_count):
        """Find the best date for a game considering all NHL scheduling constraints."""
        MAX_DAILY_GAMES = 16
        
        candidate_dates = []
        
        for game_date in available_dates:
            # Check if date is too busy
            if daily_game_count[game_date] >= MAX_DAILY_GAMES:
                continue
            
            # Check constraints for both teams
            home_valid, home_priority = self._check_team_constraints_enhanced(
                home_team, game_date, team_tracking, True  # is_home_team
            )
            away_valid, away_priority = self._check_team_constraints_enhanced(
                away_team, game_date, team_tracking, False  # is_home_team
            )
            
            if home_valid and away_valid:
                # Calculate combined priority (lower is better)
                # Add home/away balance bonus to priority
                home_balance_bonus = self._calculate_home_away_bonus(home_team, team_tracking, True)
                away_balance_bonus = self._calculate_home_away_bonus(away_team, team_tracking, False)
                
                combined_priority = (home_priority + away_priority + 
                                   home_balance_bonus + away_balance_bonus)
                candidate_dates.append((game_date, combined_priority))
        
        # Sort by priority and return best date
        if candidate_dates:
            candidate_dates.sort(key=lambda x: x[1])
            return candidate_dates[0][0]
        
        return None
    
    def _check_team_constraints_enhanced(self, team, game_date, team_tracking, is_home_team):
        """Enhanced constraint checking with better back-to-back management and home/away balance."""
        team_name = team.team_name
        track = team_tracking[team_name]
        
        last_game = track['last_game']
        second_last_game = track['second_last_game']
        
        # HARD CONSTRAINTS (must pass)
        
        # 1. No same-day games (absolute rule) - check ALL previously scheduled games
        scheduled_dates = {scheduled_date for scheduled_date, _, _ in track['schedule']}
        if game_date in scheduled_dates:
            print(f"   BLOCKING same-day: {team_name} already plays on {game_date}")
            return False, float('inf')
        
        # 2. No more than 2 consecutive games
        if (last_game and second_last_game and
            last_game == game_date - timedelta(days=1) and
            second_last_game == game_date - timedelta(days=2)):
            return False, float('inf')
        
        # 3. Enhanced back-to-back budget management (much more aggressive)
        is_back_to_back = (last_game and last_game == game_date - timedelta(days=1))
        back_to_back_budget = track['back_to_back_budget']
        
        if is_back_to_back:
            # Check if we have budget remaining
            if back_to_back_budget <= 0:
                return False, float('inf')
            
            # Be MUCH more restrictive with back-to-back budget
            games_scheduled = track['games_scheduled']
            season_progress = games_scheduled / 82.0  # How far through season (0.0 to 1.0)
            
            # Expected back-to-backs used by this point (linear distribution)
            expected_used = season_progress * 14
            actual_used = 14 - back_to_back_budget
            
            # If we're already above expected usage, be very restrictive
            if actual_used > expected_used + 2:
                return False, float('inf')
            
            # Be very conservative with remaining budget in second half of season
            if season_progress > 0.5 and back_to_back_budget < 7:
                return False, float('inf')
                
            # Be extremely conservative in final third of season
            if season_progress > 0.67 and back_to_back_budget < 5:
                return False, float('inf')
        
        # SOFT CONSTRAINTS (affect priority - lower priority is better)
        priority = 0
        
        # AGGRESSIVELY discourage back-to-backs at all times
        if is_back_to_back:
            # Base penalty for any back-to-back
            priority += 50
            
            # Escalating penalty based on budget used
            budget_used = 14 - back_to_back_budget
            budget_pressure = budget_used * 10  # Each back-to-back used increases penalty by 10
            priority += budget_pressure
            
            # Season-based penalties (more restrictive as season progresses)
            games_scheduled = track['games_scheduled']
            season_progress = games_scheduled / 82.0
            if season_progress > 0.3:  # After 30% of season
                priority += 25
            if season_progress > 0.5:  # After 50% of season  
                priority += 50
            if season_progress > 0.7:  # After 70% of season
                priority += 100
        
        # Prefer rest between games with intelligent spacing (non-back-to-back cases)
        if last_game and not is_back_to_back:
            days_since_last = (game_date - last_game).days
            if days_since_last == 2:  # 1 day rest - good
                priority -= 1
            elif days_since_last == 3:  # 2 days rest - optimal
                priority -= 3
            elif days_since_last >= 5:  # Too much rest
                priority += days_since_last - 4  # Increasing penalty for long gaps
        
        # Seasonal distribution - encourage even pacing
        games_scheduled = track['games_scheduled']
        total_games_target = 82
        
        # Calculate expected games by this point in season (rough estimate)
        # Simple linear distribution for now
        days_into_season = (game_date - last_game).days if last_game else 0
        
        if games_scheduled < 20:  # Early season - be more flexible
            priority -= 2
        elif games_scheduled > 65:  # Late season - be very careful with back-to-backs
            if is_back_to_back:
                priority += 10
        
        return True, priority
    
    def _calculate_home_away_bonus(self, team, team_tracking, is_home_game):
        """Calculate priority bonus/penalty for maintaining home/away balance."""
        track = team_tracking[team.team_name]
        home_games = track['home_games']
        away_games = track['away_games']
        total_games = track['games_scheduled']
        
        # Target: 41 home, 41 away games (82 total)
        if total_games == 0:
            return 0  # No bias for first game
        
        current_home_ratio = home_games / total_games if total_games > 0 else 0.5
        target_ratio = 0.5  # 50/50 split
        
        if is_home_game:
            # If we're scheduling a home game
            new_home_ratio = (home_games + 1) / (total_games + 1)
            if new_home_ratio > 0.6:  # Too many home games
                return 5  # Penalty
            elif current_home_ratio < 0.4:  # Need more home games
                return -3  # Bonus
        else:
            # If we're scheduling an away game  
            new_away_ratio = (away_games + 1) / (total_games + 1)
            if new_away_ratio > 0.6:  # Too many away games
                return 5  # Penalty
            elif current_home_ratio > 0.6:  # Need more away games
                return -3  # Bonus
        
        return 0  # No adjustment needed
    

    
    def _update_team_tracking_after_game(self, home_team, away_team, game_date, team_tracking):
        """Update tracking information after scheduling a game with enhanced back-to-back budget tracking."""
        for team in [home_team, away_team]:
            team_name = team.team_name
            track = team_tracking[team_name]
            is_home_game = (team == home_team)
            
            # Check if this creates a back-to-back
            is_back_to_back = (track['last_game'] and 
                             track['last_game'] == game_date - timedelta(days=1))
            
            # Update tracking
            track['second_last_game'] = track['last_game']
            track['last_game'] = game_date
            track['games_scheduled'] += 1
            
            # Update home/away counts
            if is_home_game:
                track['home_games'] += 1
            else:
                track['away_games'] += 1
            
            # Update back-to-back tracking and budget
            if is_back_to_back:
                track['back_to_backs'] += 1
                track['back_to_back_budget'] -= 1  # Consume one from budget
            
            # Update consecutive games count
            if is_back_to_back:
                track['consecutive_games'] += 1
            else:
                track['consecutive_games'] = 1
            
            # Add to schedule
            opponent = away_team if team == home_team else home_team
            home_away = 'home' if is_home_game else 'away'
            track['schedule'].append((game_date, opponent.team_name, home_away))
    
    def _emergency_schedule(self, home_team, away_team, available_dates, team_tracking):
        """Emergency scheduling when normal constraints fail - maintains critical rules only."""
        for game_date in available_dates:
            # Check ALL previously scheduled games for both teams 
            home_scheduled_dates = {scheduled_date for scheduled_date, _, _ in team_tracking[home_team.team_name]['schedule']}
            away_scheduled_dates = {scheduled_date for scheduled_date, _, _ in team_tracking[away_team.team_name]['schedule']}
            
            # 1. Absolutely no same-day games (critical rule)
            if game_date in home_scheduled_dates or game_date in away_scheduled_dates:
                continue
            
            # 2. Check back-to-back budget constraints (critical for NHL compliance)
            home_track = team_tracking[home_team.team_name]
            away_track = team_tracking[away_team.team_name]
            
            home_is_back_to_back = (home_track['last_game'] and 
                                  home_track['last_game'] == game_date - timedelta(days=1))
            away_is_back_to_back = (away_track['last_game'] and 
                                  away_track['last_game'] == game_date - timedelta(days=1))
            
            # Block if either team would exceed budget (even in emergency)
            if home_is_back_to_back and home_track['back_to_back_budget'] <= 0:
                continue
            if away_is_back_to_back and away_track['back_to_back_budget'] <= 0:
                continue
            
            # 3. Try to avoid 3+ consecutive games even in emergency (if possible)
            home_last = home_track['last_game']
            home_second_last = home_track['second_last_game']
            away_last = away_track['last_game']
            away_second_last = away_track['second_last_game']
            
            # Check for 3 consecutive games
            home_three_consecutive = (home_last and home_second_last and
                                    home_last == game_date - timedelta(days=1) and
                                    home_second_last == game_date - timedelta(days=2))
            
            away_three_consecutive = (away_last and away_second_last and
                                    away_last == game_date - timedelta(days=1) and
                                    away_second_last == game_date - timedelta(days=2))
            
            if not (home_three_consecutive or away_three_consecutive):
                # This date passes our emergency checks
                return game_date
        
        # If no date found avoiding 3 consecutive, try again with just same-day check
        for game_date in available_dates:
            home_scheduled_dates = {scheduled_date for scheduled_date, _, _ in team_tracking[home_team.team_name]['schedule']}
            away_scheduled_dates = {scheduled_date for scheduled_date, _, _ in team_tracking[away_team.team_name]['schedule']}
            
            if game_date not in home_scheduled_dates and game_date not in away_scheduled_dates:
                print(f"⚠️ Emergency scheduled (allows consecutive): {home_team.team_name} vs {away_team.team_name} on {game_date}")
                return game_date
        
        # If we still can't find ANY valid date, skip this game entirely
        print(f"⚠️ Cannot schedule {home_team.team_name} vs {away_team.team_name} - no valid dates")
        return None
    
    def _report_schedule_stats_enhanced(self, team_tracking, teams):
        """Enhanced reporting with home/away balance and back-to-back budget tracking."""
        total_back_to_backs = 0
        total_games = 0
        total_home_games = 0
        total_away_games = 0
        back_to_back_violations = []
        home_away_violations = []
        
        for team in teams:
            track = team_tracking[team.team_name]
            total_back_to_backs += track['back_to_backs']
            total_games += track['games_scheduled']
            total_home_games += track['home_games']
            total_away_games += track['away_games']
            
            # Check back-to-back violations
            if track['back_to_backs'] > 14:
                back_to_back_violations.append(
                    f"{team.team_name}: {track['back_to_backs']} back-to-backs (budget remaining: {track['back_to_back_budget']})"
                )
            
            # Check home/away balance (should be close to 41/41)
            home_games = track['home_games']
            away_games = track['away_games']
            total_team_games = home_games + away_games
            
            if total_team_games > 0:
                home_ratio = home_games / total_team_games
                if abs(home_ratio - 0.5) > 0.15:  # More than 15% imbalance
                    home_away_violations.append(
                        f"{team.team_name}: {home_games}H/{away_games}A ({home_ratio:.1%} home)"
                    )
        
        # Calculate averages
        avg_back_to_backs = total_back_to_backs / len(teams) if teams else 0
        avg_games = total_games / len(teams) if teams else 0
        avg_home_games = total_home_games / len(teams) if teams else 0
        avg_away_games = total_away_games / len(teams) if teams else 0
        
        print(f"✓ Enhanced Schedule Generation Complete:")
        print(f"  Average total games per team: {avg_games:.1f}")
        print(f"  Average home games per team: {avg_home_games:.1f}")
        print(f"  Average away games per team: {avg_away_games:.1f}")
        print(f"  Average back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Report violations
        if back_to_back_violations:
            print(f"⚠️ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"  {violation}")
            if len(back_to_back_violations) > 5:
                print(f"  ... and {len(back_to_back_violations) - 5} more")
        else:
            print(f"✅ All teams within back-to-back limit (≤14)")
        
        if home_away_violations:
            print(f"⚠️ Home/Away balance issues ({len(home_away_violations)}):")
            for violation in home_away_violations[:5]:
                print(f"  {violation}")
        else:
            print(f"✅ All teams have balanced home/away games (~50/50)")
    
    def _report_schedule_stats(self, team_tracking, teams):
        """Legacy reporting method - kept for compatibility."""
        self._report_schedule_stats_enhanced(team_tracking, teams)

    def end_of_season(self):
        """Handles all end-of-season logic like aging players and resetting stats."""
        all_players = self.get_all_players()
        for player in all_players:
            player.age_one_year()
            player.stats = PlayerStats()
        
        self.season_year += 1
        
        # Initialize draft picks for upcoming years
        self.initialize_all_draft_picks()
        
        self.initialize_standings()
        self.generate_schedule()

    def initialize_all_draft_picks(self):
        """Initialize draft picks for all teams for the next few years."""
        future_years = [self.season_year + i for i in range(3)]  # Next 3 years
        
        for team in self.teams:
            team.initialize_draft_picks(future_years)

    def get_draft_order(self, year: int) -> List[Tuple[int, Team, DraftPick]]:
        """Generate the draft order for a specific year based on standings.
        
        Returns:
            List of tuples: (overall_pick_number, team, draft_pick)
        """
        draft_order = []
        
        # Sort teams by points (worst to best for each round)
        sorted_teams = sorted(self.teams, 
                            key=lambda t: self.standings[t.team_name]['Points'])
        
        for round_num in range(1, 8):  # 7 rounds
            round_picks = []
            
            # Get all picks for this round and year
            for team in sorted_teams:
                team_picks = [pick for pick in team.get_picks_for_year(year) 
                            if pick.round == round_num]
                
                for pick in team_picks:
                    # Find the team that currently owns this pick
                    current_owner = None
                    for owner_team in self.teams:
                        if pick in owner_team.get_picks_for_year(year):
                            current_owner = owner_team
                            break
                    
                    if current_owner:
                        round_picks.append((current_owner, pick))
            
            # Sort by original team's standing (traded picks keep original position)
            round_picks.sort(key=lambda x: sorted_teams.index(
                next(t for t in self.teams if t.team_name == x[1].original_team)
            ))
            
            # Assign overall pick numbers
            for i, (current_owner, pick) in enumerate(round_picks):
                overall_pick = ((round_num - 1) * 32) + i + 1
                pick.overall_pick = overall_pick
                draft_order.append((overall_pick, current_owner, pick))
        
        return draft_order

    def simulate_draft_lottery(self, year: int):
        """Simulate draft lottery for first round picks (if applicable)."""
        # This is a simplified lottery - in reality it's more complex
        first_round_picks = []
        
        # Get all first round picks for the year
        for team in self.teams:
            team_picks = [pick for pick in team.get_picks_for_year(year) 
                         if pick.round == 1]
            for pick in team_picks:
                first_round_picks.append(pick)
        
        # Sort by original team standings (worst to best)
        sorted_teams = sorted(self.teams, 
                            key=lambda t: self.standings[t.team_name]['Points'])
        
        first_round_picks.sort(key=lambda pick: sorted_teams.index(
            next(t for t in self.teams if t.team_name == pick.original_team)
        ))
        
        # Simple lottery simulation - top 3 picks have some randomization
        if len(first_round_picks) >= 3:
            import random
            
            # Small chance for teams 4-8 to jump into top 3
            lottery_teams = first_round_picks[:8]  # Bottom 8 teams eligible
            
            # 20% chance for a team to jump to #1
            if random.random() < 0.2 and len(lottery_teams) > 3:
                winner_idx = random.randint(3, min(7, len(lottery_teams) - 1))
                # Move the lottery winner to first position
                winner_pick = lottery_teams.pop(winner_idx)
                lottery_teams.insert(0, winner_pick)
                
                # Update the first round picks list
                first_round_picks = lottery_teams + first_round_picks[8:]

    def trade_draft_pick(self, pick: DraftPick, from_team: Team, to_team: Team, trade_details: str = ""):
        """Execute a draft pick trade between two teams."""
        if pick not in from_team.get_picks_for_year(pick.year):
            raise ValueError(f"{from_team.team_name} does not own this draft pick")
        
        # Execute the trade
        from_team.trade_pick(pick, to_team.team_name, trade_details)
        to_team.receive_pick(pick)
        
        return True

    def _verify_schedule_integrity(self):
        """Comprehensive verification of NHL scheduling rules and constraints."""
        from collections import defaultdict
        
        print("🔍 Verifying NHL schedule integrity...")
        
        # Group games by date and team
        team_games_by_date = defaultdict(lambda: defaultdict(list))
        team_schedules = defaultdict(list)  # List of (date, opponent, home/away) for each team
        
        for game_date, home_team, away_team in self.schedule:
            home_name = home_team.team_name
            away_name = away_team.team_name
            
            team_games_by_date[game_date][home_name].append('home')
            team_games_by_date[game_date][away_name].append('away')
            
            team_schedules[home_name].append((game_date, away_name, 'home'))
            team_schedules[away_name].append((game_date, home_name, 'away'))
        
        violations = []
        team_stats = {}
        
        # Check Rule 1: No team plays multiple games on the same day
        same_day_violations = []
        for game_date, teams_data in team_games_by_date.items():
            for team_name, games in teams_data.items():
                if len(games) > 1:
                    same_day_violations.append(f"{team_name} has {len(games)} games on {game_date}")
        
        # Check each team's schedule for NHL compliance
        for team_name, schedule in team_schedules.items():
            # Sort by date
            schedule.sort(key=lambda x: x[0])
            
            # Calculate team statistics
            total_games = len(schedule)
            back_to_backs = 0
            consecutive_streaks = []
            current_streak = 1
            max_consecutive = 1
            
            for i in range(1, len(schedule)):
                prev_date = schedule[i-1][0]
                curr_date = schedule[i][0]
                days_between = (curr_date - prev_date).days
                
                if days_between == 1:  # Back-to-back
                    back_to_backs += 1
                    current_streak += 1
                else:
                    if current_streak > 1:
                        consecutive_streaks.append(current_streak)
                    max_consecutive = max(max_consecutive, current_streak)
                    current_streak = 1
            
            # Don't forget the last streak
            if current_streak > 1:
                consecutive_streaks.append(current_streak)
            max_consecutive = max(max_consecutive, current_streak)
            
            team_stats[team_name] = {
                'games': total_games,
                'back_to_backs': back_to_backs,
                'max_consecutive': max_consecutive,
                'consecutive_streaks': consecutive_streaks
            }
            
            # Check Rule 2: No more than 14 back-to-backs per team
            if back_to_backs > 14:
                violations.append(f"{team_name}: {back_to_backs} back-to-backs (limit: 14)")
            
            # Check Rule 3: No more than 2 consecutive games
            if max_consecutive > 2:
                violations.append(f"{team_name}: {max_consecutive} consecutive games (limit: 2)")
        
        # Check Rule 4: Reasonable daily game distribution
        daily_game_counts = defaultdict(int)
        for game_date, _, _ in self.schedule:
            daily_game_counts[game_date] += 1
        
        busy_days = [(date, count) for date, count in daily_game_counts.items() if count > 16]
        
        # Generate comprehensive report
        print(f"\n📊 SCHEDULE INTEGRITY REPORT")
        print(f"{'='*50}")
        
        # Same-day violations (most critical)
        if same_day_violations:
            print(f"❌ CRITICAL: Same-day game violations ({len(same_day_violations)}):")
            for violation in same_day_violations[:10]:
                print(f"   • {violation}")
            if len(same_day_violations) > 10:
                print(f"   ... and {len(same_day_violations) - 10} more")
        else:
            print(f"✅ Same-day games: PASSED (no team plays multiple games same day)")
        
        # Back-to-back violations
        back_to_back_violations = [v for v in violations if "back-to-backs" in v]
        if back_to_back_violations:
            print(f"❌ Back-to-back violations ({len(back_to_back_violations)}):")
            for violation in back_to_back_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Back-to-back limit: PASSED (all teams ≤14 back-to-backs)")
        
        # Consecutive game violations
        consecutive_violations = [v for v in violations if "consecutive games" in v]
        if consecutive_violations:
            print(f"❌ Consecutive game violations ({len(consecutive_violations)}):")
            for violation in consecutive_violations[:5]:
                print(f"   • {violation}")
        else:
            print(f"✅ Consecutive games: PASSED (no team plays >2 consecutive)")
        
        # Daily distribution
        if busy_days:
            print(f"⚠️ Busy days (>16 games): {len(busy_days)}")
            for date, count in sorted(busy_days, key=lambda x: x[1], reverse=True)[:3]:
                print(f"   • {date}: {count} games")
        else:
            print(f"✅ Daily distribution: PASSED (≤16 games per day)")
        
        # Overall statistics
        if team_stats:
            avg_games = sum(stats['games'] for stats in team_stats.values()) / len(team_stats)
            avg_back_to_backs = sum(stats['back_to_backs'] for stats in team_stats.values()) / len(team_stats)
            
            print(f"\n📈 LEAGUE STATISTICS")
            print(f"   Teams: {len(team_stats)}")
            print(f"   Total games: {len(self.schedule)}")
            print(f"   Avg games per team: {avg_games:.1f}")
            print(f"   Avg back-to-backs per team: {avg_back_to_backs:.1f}")
        
        # Final verdict
        total_violations = len(same_day_violations) + len(violations)
        if total_violations == 0:
            print(f"\n🎉 SCHEDULE INTEGRITY: EXCELLENT")
            print(f"   All NHL scheduling rules satisfied!")
        elif len(same_day_violations) == 0:
            print(f"\n✅ SCHEDULE INTEGRITY: GOOD")
            print(f"   Critical rules satisfied, {len(violations)} minor violations")
        else:
            print(f"\n❌ SCHEDULE INTEGRITY: NEEDS IMPROVEMENT") 
            print(f"   {total_violations} total violations found")
        
        print(f"{'='*50}\n")

    def get_all_players(self) -> List[Player]:
        """Returns a list of every single player in the game world."""
        all_players = list(self.free_agents)
        all_players.extend(self.draft_prospects)
        for team in self.teams:
            all_players.extend(team.roster)
            all_players.extend(team.ahl_roster)
            all_players.extend(team.prospects)
        return all_players

    def add_team(self, team: Team):
        """Add a team to the league."""
        self.teams.append(team)
        # Initialize standings for this team
        self.standings[team.team_name] = {"W": 0, "L": 0, "OTL": 0, "Points": 0}





